"""Independent saved-source integrity audit for C143766 pedestrian attempts.

This verifies original identity, sealed bytes and body motion. Full video decode,
actual pixel visibility, legal context and acceptance are separate later gates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

from corridor_construction import measure_original, validate_scene
from native_capture import CAMERA_SPECS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _source(root, name, expected):
    path = (root/name).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("missing sealed original source: "+name)
    if sha(path) != expected:
        raise ValueError("sealed original source hash differs: "+name)
    return path


def verify_frame_joins(scene, mapping, bodies, trace, joins, *, diagnostic_test=False):
    """Cross-check every retained Native identity without trusting case labels."""
    count = len(mapping)
    if count < 3 or not all(len(group) == count for group in (bodies, trace, joins)):
        raise ValueError("original frame sources have missing rows")
    first = mapping[0]["carla_frame"]
    actor_id = bodies[0].get("actor_id", 7) if diagnostic_test else bodies[0]["actor_id"]
    for index, (frame_map, body, observation, joined) in enumerate(
            zip(mapping, bodies, trace, joins)):
        frame = first+index
        time_s = frame_map["time_s"]
        if (frame_map.get("video_frame") != index or
                frame_map.get("carla_frame") != frame or
                frame_map.get("native_frame") != frame or
                not isinstance(time_s, (int, float)) or not math.isfinite(time_s)):
            raise ValueError("original frame map is not consecutive")
        if index and abs(time_s-mapping[index-1]["time_s"]-.05) > .005:
            raise ValueError("original frame map timing is not 20 Hz")
        if (body.get("case_id") != scene["case_id"] or
                (not diagnostic_test and body.get("source_kind") != "original_native_world_vertices") or
                body.get("actor_id", 7) != actor_id or body.get("frame") != frame or
                abs(body.get("time_s", float("inf"))-time_s) > 1e-4):
            raise ValueError("original walker body identity or timestamp differs")
        if (observation.get("actor_id", 7) != actor_id or
                observation.get("frame") != frame or
                abs(observation.get("time_s", float("inf"))-time_s) > 1e-4):
            raise ValueError("original trace identity or timestamp differs")
        center = observation.get("position_m")
        if (not isinstance(center, list) or len(center) != 3 or
                not all(isinstance(v, (int, float)) and math.isfinite(v) for v in center)):
            raise ValueError("original trace lacks finite walker position")
        footprint = body.get("body_xy_m", [])
        if (len(footprint) != 4 or
                any(len(point) != 2 for point in footprint) or
                not all(min(point[axis] for point in footprint) <= center[axis] <=
                        max(point[axis] for point in footprint) for axis in (0, 1))):
            raise ValueError("original trace walker position leaves body footprint")
        if (joined.get("case_id") != scene["case_id"] or
                joined.get("walker_actor_id", 7) != actor_id or
                joined.get("frame") != frame or
                abs(joined.get("time_s", float("inf"))-time_s) > 1e-4 or
                set(joined.get("cameras", {})) != set(CAMERA_SPECS)):
            raise ValueError("original four-camera join identity differs")
        for name, (width, height) in CAMERA_SPECS.items():
            camera = joined["cameras"][name]
            if (camera.get("frame") != frame or camera.get("width") != width or
                    camera.get("height") != height or
                    camera.get("pixel_format") != "bgra" or
                    camera.get("bytes") != width*height*4):
                raise ValueError("original camera source metadata differs: "+name)
    measured = measure_original(scene, bodies)
    return {"frame_count": count, "walker_actor_id": actor_id,
            "motion_measurement": measured, "time_join_passed": True,
            "four_camera_metadata_join_passed": True,
            "physical_acceptance_claimed": False}


def verify_saved_sources(attempt):
    """Reopen and verify every original source listed in the pinned capture seal."""
    root = Path(attempt).resolve()
    seal = json.loads((root/"capture-seal.json").read_text())
    provenance = json.loads((root/"acquisition-provenance.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "native" or seal.get("diagnostic_fixture") or
            provenance.get("provenance_kind") != "native" or
            provenance.get("diagnostic_fixture") is not False or
            seal.get("restoration", {}).get("restored") is not True or
            seal.get("encoder_exit_codes") != {name: 0 for name in CAMERA_SPECS}):
        raise ValueError("sealed Native acquisition and restoration required")
    sources = seal.get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("sealed source inventory missing")
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    if digest != seal.get("source_digest"):
        raise ValueError("sealed source inventory digest differs")
    for name, expected in sources.items():
        _source(root, name, expected)
    required = {"scene.json", "candidate-corridor.xodr", "trace.jsonl",
                "walker-body-history.jsonl", "video_frames.jsonl",
                "camera-frame-joins.jsonl", "acquisition.json",
                *(name+".mkv" for name in CAMERA_SPECS)}
    if not required <= set(sources):
        raise ValueError("sealed original source inventory is incomplete")
    scene = json.loads((root/"scene.json").read_text())
    validate_scene(scene)
    if sha(root/"candidate-corridor.xodr") != scene["map_source_sha256"]:
        raise ValueError("sealed scene and authored map differ")
    acquisition = json.loads((root/"acquisition.json").read_text())
    if set(acquisition) != (required-{"acquisition.json"}) | {"road.xodr"}:
        raise ValueError("original acquisition inventory differs")
    for name, item in acquisition.items():
        if item.get("kind") != "original_native" or item.get("sha256") != sha(root/name):
            raise ValueError("original acquisition source differs: "+name)
    result = verify_frame_joins(scene, rows(root/"video_frames.jsonl"),
                                rows(root/"walker-body-history.jsonl"),
                                rows(root/"trace.jsonl"),
                                rows(root/"camera-frame-joins.jsonl"))
    if result["frame_count"] != seal.get("frames"):
        raise ValueError("sealed frame count differs")
    result.update({"format": "c143766-saved-original-source-audit-v1",
                   "case_id": scene["case_id"],
                   "capture_seal_sha256": sha(root/"capture-seal.json"),
                   "source_digest": digest,
                   "original_source_integrity_passed": True,
                   "full_video_decode_passed": False,
                   "actual_pixel_visibility_verified": False,
                   "legal_judgment": "unresolved"})
    return result


def verify_diagnostic_sources(attempt):
    """Check a marked software fixture without treating it as Native evidence."""
    root = Path(attempt).resolve()
    seal = json.loads((root/"capture-seal.json").read_text())
    provenance = json.loads((root/"acquisition-provenance.json").read_text())
    if (seal.get("format") != "worker-sealed-capture" or
            seal.get("provenance_kind") != "synthetic_fixture" or
            seal.get("diagnostic_fixture") is not True or
            seal.get("restoration", {}).get("restored") is not True or
            provenance.get("provenance_kind") != "synthetic_fixture" or
            provenance.get("diagnostic_fixture") is not True):
        raise ValueError("diagnostic fixture provenance required")
    sources = seal.get("sources", {})
    digest = hashlib.sha256(json.dumps(sources, sort_keys=True,
                            separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    if digest != seal.get("source_digest"):
        raise ValueError("diagnostic source inventory digest differs")
    required = {"scene.json", "candidate-corridor.xodr", "trace.jsonl",
                "walker-body-history.jsonl", "video_frames.jsonl",
                "camera-frame-joins.jsonl", "analysis-report.json", "result.json",
                *(name+".mkv" for name in CAMERA_SPECS)}
    if not required <= set(sources):
        raise ValueError("diagnostic source inventory incomplete")
    for name, expected in sources.items():
        _source(root, name, expected)
    scene = json.loads((root/"scene.json").read_text())
    validate_scene(scene)
    if sha(root/"candidate-corridor.xodr") != scene["map_source_sha256"]:
        raise ValueError("diagnostic scene and map differ")
    result = verify_frame_joins(scene, rows(root/"video_frames.jsonl"),
                                rows(root/"walker-body-history.jsonl"),
                                rows(root/"trace.jsonl"),
                                rows(root/"camera-frame-joins.jsonl"),
                                diagnostic_test=True)
    if result["frame_count"] != seal.get("frames"):
        raise ValueError("diagnostic frame count differs")
    result.update({"format": "c143766-diagnostic-source-audit-v1",
                   "case_id": scene["case_id"],
                   "capture_seal_sha256": sha(root/"capture-seal.json"),
                   "source_digest": digest,
                   "original_source_integrity_passed": True,
                   "full_video_decode_passed": False,
                   "actual_pixel_visibility_verified": False,
                   "legal_judgment": "unresolved"})
    return result


def decode_original_videos(attempt, *, diagnostic_test=False):
    """Run pinned complete decodes after source sealing, retaining exact receipts."""
    source_check = (verify_diagnostic_sources(attempt) if diagnostic_test else
                    verify_saved_sources(attempt))
    root = Path(attempt).resolve()
    repository = Path(__file__).resolve().parents[2]
    safe_root = (repository/".runtime-work").resolve()
    if not root.is_relative_to(safe_root):
        raise ValueError("original video decode requires .runtime-work attempt")
    os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(safe_root/"c143766-audit-runtime")
    runtime_pipeline = repository/"runtime/scenario_pipeline"
    if str(runtime_pipeline) not in sys.path:
        sys.path.insert(0, str(runtime_pipeline))
    from worker_exchange.media import audit, check_four_view_sources

    videos = {name: root/(name+".mkv") for name in CAMERA_SPECS}
    check_four_view_sources(videos)
    mapping_sha = sha(root/"video_frames.jsonl")
    receipt_dir = safe_root/"c143766-audit-receipts"/sha(root/"capture-seal.json")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    decoded = {}
    for name, (width, height) in CAMERA_SPECS.items():
        receipt_path = receipt_dir/("source-decode-"+name+".json")
        receipt = audit(videos[name], source_check["frame_count"],
                        mapping_sha256=mapping_sha, receipt=receipt_path)
        if receipt.get("dimensions") != [width, height]:
            raise ValueError("decoded camera dimensions differ: "+name)
        decoded[name] = {"video_sha256": receipt["video_sha256"],
                         "receipt_sha256": sha(receipt_path),
                         "decoded_frames": receipt["frames"]}
    return {**source_check, "full_video_decode_passed": True,
            "source_decode_receipts": decoded,
            "actual_pixel_visibility_verified": False,
            "physical_acceptance_claimed": False}


def audit(attempt, *, diagnostic_test=False):
    """Cross-check sealed sources, decoded media and saved physical status."""
    root = Path(attempt).resolve()
    decoded = decode_original_videos(root, diagnostic_test=diagnostic_test)
    report = json.loads((root/"analysis-report.json").read_text())
    result = json.loads((root/"result.json").read_text())
    measured = decoded["motion_measurement"]
    selected = report.get("measurements", {}).get("pedestrian_full_body_band_occupancy", {})
    if (report.get("case_id") != decoded["case_id"] or
            result.get("case_id") != decoded["case_id"] or
            selected.get("value") != measured or
            result.get("measured_values") != measured):
        raise ValueError("saved original measurement differs from independent body audit")
    checks = result.get("physical_checks", {})
    maneuver = checks.get("maneuver", {})
    if (maneuver.get("status") not in ("met", "not_met", "unverified") or
            result.get("maneuver_completed") != (maneuver["status"] == "met") or
            not result.get("target_checks") or
            result["target_checks"][0].get("measured") != measured["all_body_inside_route_band"]):
        raise ValueError("saved physical completion or body target differs")
    if diagnostic_test and (result.get("provenance_kind") != "synthetic_fixture" or
                            result.get("diagnostic_fixture") is not True):
        raise ValueError("diagnostic result provenance differs")
    return {**decoded, "format": "worker-delivery-audit",
            "diagnostic_audit_test_passed": diagnostic_test,
            "physical_completion_status": maneuver["status"],
            "actual_pixels_fully_decoded": True,
            "actual_pixel_visibility_verified": False,
            "legal_verdict_claimed": False,
            "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), indent=2))


if __name__ == "__main__":
    main()
