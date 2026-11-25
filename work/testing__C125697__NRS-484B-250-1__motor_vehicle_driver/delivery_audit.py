"""Independent original-source gate for C125697 median-opening delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image

import median_opening

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
DIMENSIONS = {"overview": (1920, 1080), "approach": (1280, 720),
              "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
SOURCE_NAMES = ("native_trace", "opendrive", "device_inventory") + tuple(
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


def audit_sources(attempt, case_id, expected_frames=900):
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
    observations = median_opening.measure_saved(read(trace_path), scene,
                                                 expected_frames=expected_frames)
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
            "highway_source_sha256": sha(root / "highway_identity.json"),
            "manifest_sha256": sha(manifest_path)}


def _pixels(root, role, expected_frames=900, dimensions=None):
    path = required(root, role + ".mkv")
    width, height = dimensions or DIMENSIONS[role]
    probe = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,avg_frame_rate",
        "-of", "json", str(path)], capture_output=True, text=True, check=True,
        timeout=90)
    streams = json.loads(probe.stdout).get("streams", [])
    if (len(streams) != 1 or streams[0].get("codec_name") != "ffv1" or
            (streams[0].get("width"), streams[0].get("height")) != (width, height) or
            streams[0].get("avg_frame_rate") != "20/1"):
        raise ValueError("original camera codec/dimensions/fps differ: " + role)
    frame_map = read(required(root, "frame-map-" + role + ".json"))
    global_map = [json.loads(line) for line in required(root, "video_frames.jsonl").read_text().splitlines()]
    if len(frame_map) != expected_frames or len(global_map) != expected_frames:
        raise ValueError("original camera frame map incomplete: " + role)
    for index, (local, global_row) in enumerate(zip(frame_map, global_map)):
        if (local.get("video_frame") != index or
                local.get("carla_frame") != global_row.get("carla_frame") or
                local.get("time_s") != global_row.get("time_s")):
            raise ValueError("original camera frame map differs: " + role)
    indices = {0, expected_frames // 2, expected_frames - 1}
    samples = {}
    for index in indices:
        name = f"sample-{role}-{index:06d}.png"
        with Image.open(required(root, name)) as image:
            if image.size != (width, height):
                raise ValueError("original PNG dimensions differ: " + name)
            samples[index] = image.convert("RGB").tobytes()
    frame_bytes = width * height * 3
    process = subprocess.Popen([
        "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
        "-xerror", "-i", str(path), "-vsync", "0", "-f", "rawvideo",
        "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    digest = hashlib.sha256()
    try:
        for index in range(expected_frames):
            data = process.stdout.read(frame_bytes)
            if len(data) != frame_bytes:
                raise ValueError("original camera full decode incomplete: " + role)
            digest.update(data)
            if index in samples:
                if data != samples[index]:
                    raise ValueError("original PNG/video pixel join differs: " + role)
                if len(set(data[::max(1, len(data) // 8192)])) < 5:
                    raise ValueError("original view lacks independently visible pixels: " + role)
        if process.stdout.read(1) or process.wait(timeout=120) != 0:
            raise ValueError("original camera full decode count/error differs: " + role)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        process.stdout.close()
        process.stderr.close()
    return {"frame_count": expected_frames, "width": width, "height": height,
            "fps": 20, "decoded_rgb_sha256": digest.hexdigest(),
            "sample_frames": sorted(indices)}


def audit_delivery(attempt, processing, case_id):
    root = Path(attempt)
    if (root / "fixture-provenance.json").exists():
        raise ValueError("diagnostic fixture cannot establish Native delivery")
    source = audit_sources(root, case_id)
    seal_path = required(root, "capture-seal.json")
    seal = read(seal_path)
    if (seal.get("provenance_kind") != "native" or
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
    pixels = {role: _pixels(root, role) for role in CAMERAS}
    return {"format": "worker-delivery-audit", "passed": True,
            "case_id": case_id, "original_sources": source,
            "capture_seal_sha256": sha(seal_path),
            "processing_sha256": sha(processing), "original_video_decode": pixels,
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
