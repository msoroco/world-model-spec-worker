"""Independent original-source gate for C125697 median-opening delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import median_source

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCE_NAMES = ("native_trace", "opendrive", "device_inventory", "highway_identity") + tuple(
    "camera_" + role for role in CAMERAS)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError("sealed original missing or changed: " + name)
    return path


def audit_sources(attempt, case_id, expected_frames=900, *, diagnostic=False):
    root = Path(attempt)
    scene = read(required(root, "scene.json"))
    if scene.get("case_id") != case_id:
        raise ValueError("wrong exact median-opening case")
    manifest_path = required(root, "original-source-manifest.json")
    manifest = read(manifest_path)
    if manifest.get("case_id") != case_id or manifest.get("frame_count") != expected_frames:
        raise ValueError("original source manifest case/frame count differs")
    if set(manifest.get("sources", {})) != set(SOURCE_NAMES):
        raise ValueError("original source manifest inventory differs")
    for name, item in manifest["sources"].items():
        path = required(root, item["path"])
        if sha(path) != item["sha256"]:
            raise ValueError("sealed original missing or changed: " + item["path"])
    highway = read(required(root, "highway_identity.json"))
    if (highway.get("ego_highway") != scene.get("ego_highway") or
            highway.get("other_highway") != scene.get("other_highway") or
            highway.get("public_access_confirmed") is not True):
        raise ValueError("original public-highway source differs")
    trace_path = required(root, manifest["sources"]["native_trace"]["path"])
    audited = median_source.audit_saved_sources(root, manifest, scene,
                                               diagnostic_fixture=diagnostic)
    observations = audited["observations"]
    geometry = read(required(root, "crossing_geometry.json"))
    box = scene["crossing"]["bounds_xy_m"]
    if (geometry.get("intersection_xy_m") != [[box[0], box[1]], [box[2], box[1]],
                                               [box[2], box[3]], [box[0], box[3]]] or
            geometry.get("source_opendrive_sha256") != scene["crossing"]["opendrive_sha256"]):
        raise ValueError("original crossing geometry differs from reviewed site")
    mapping = [json.loads(line) for line in required(root, "video_frames.jsonl").read_text().splitlines()]
    trace = [json.loads(line) for line in required(root, "trace.jsonl").read_text().splitlines()]
    crossing = [json.loads(line) for line in required(root, "crossing_history.jsonl").read_text().splitlines()]
    native = read(trace_path)["frames"]
    if len(mapping) != expected_frames or len(trace) != expected_frames or len(crossing) != expected_frames:
        raise ValueError("original camera frame map incomplete")
    for index, (video, motion, body, source) in enumerate(zip(mapping, trace, crossing, native)):
        if (video.get("video_frame") != index or
                video.get("carla_frame") != source["native_frame_id"] or
                video.get("time_s") != source["native_elapsed_seconds"] or
                motion.get("frame") != source["native_frame_id"] or
                motion.get("time_s") != source["native_elapsed_seconds"] or
                body.get("frame") != source["native_frame_id"] or
                body.get("time_s") != source["native_elapsed_seconds"] or
                body.get("ego_vertices_m") != source["ego"]["body_vertices_xy_m"]):
            raise ValueError("original camera/body timestamp join differs")
    return {"case_id": case_id, "observations": observations,
            "source_sha256": {name: item["sha256"] for name, item in manifest["sources"].items()},
            "frame_map_sha256": sha(root / "video_frames.jsonl"),
            "crossing_history_sha256": sha(root / "crossing_history.jsonl"),
            "crossing_geometry_sha256": sha(root / "crossing_geometry.json"),
            "highway_source_sha256": sha(root / "highway_identity.json"),
            "manifest_sha256": sha(manifest_path)}


def _pixels(path):
    result = subprocess.run([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-i", str(path), "-vf", "scale=64:36", "-frames:v", "1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True, timeout=90)
    data = result.stdout
    if len(data) != 64 * 36 * 3 or len(set(data)) < 5 or sum(value > 12 for value in data) < len(data) // 10:
        raise ValueError("original view lacks independently visible pixels: " + path.name)
    return hashlib.sha256(data).hexdigest()


def audit_delivery(attempt, processing, case_id):
    root = Path(attempt)
    if (root / "fixture-provenance.json").exists():
        raise ValueError("diagnostic fixture cannot establish Native delivery")
    source = audit_sources(root, case_id)
    seal_path = required(root, "capture-seal.json")
    seal = read(seal_path)
    if (seal.get("provenance_kind") != "native" or
            seal.get("diagnostic_fixture") is not False or seal.get("frames") != 900 or
            seal.get("events") != ["capture_finished", "encoders_closed", "restoration_verified"] or
            seal.get("restoration", {}).get("restored") is not True):
        raise ValueError("Native capture lifecycle incomplete")
    for name, checksum in seal.get("sources", {}).items():
        if sha(required(root, name)) != checksum:
            raise ValueError("sealed original missing or changed: " + name)
    exit_receipt = read(required(root, "native-exit.json"))
    if exit_receipt.get("capture_seal_sha256") != sha(seal_path):
        raise ValueError("Native exit does not bind capture seal")
    owner = read(required(root, "owner-release.json"))
    if (owner.get("event") != "owner_released" or owner.get("operator_attested") is not True or
            owner.get("native_exit_sha256") != sha(root / "native-exit.json")):
        raise ValueError("Native owner release absent or stale")
    proof = read(processing)
    if (proof.get("format") != "worker-saved-processing" or proof.get("passed") is not True or
            proof.get("recorded_only") is not True or proof.get("originals_preserved") is not True or
            proof.get("case_id") != case_id or proof.get("missing_evidence") is not False):
        raise ValueError("saved processing proof absent or failed")
    result_path = Path(proof["result"])
    result = read(required(result_path.parent, result_path.name))
    if proof.get("result_sha256") != sha(result_path) or result.get("case_id") != case_id:
        raise ValueError("saved selected result changed")
    if (not all(check.get("matched") is True for check in result.get("target_checks", [])) or
            len(result.get("target_checks", [])) < 2 or
            not all(result.get(key) is True for key in
                    ("setup_confirmed", "behavior_attempted", "maneuver_completed"))):
        raise ValueError("selected physical response incomplete")
    physical = result.get("physical_checks", {})
    if any(physical.get(key, {}).get("status") != "met"
           for key in ("setup", "target", "maneuver", "attempt")):
        raise ValueError("original physical checks incomplete")
    pixels = {role: _pixels(required(root, role + ".mkv")) for role in CAMERAS}
    return {"format": "worker-delivery-audit", "passed": True,
            "case_id": case_id, "original_sources": source,
            "capture_seal_sha256": sha(seal_path),
            "processing_sha256": sha(processing), "pixel_first_frame_sha256": pixels,
            "legal_verdict": None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--processing", required=True, type=Path)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    print(json.dumps(audit_delivery(args.attempt, args.processing, args.case), indent=2))


if __name__ == "__main__":
    main()
