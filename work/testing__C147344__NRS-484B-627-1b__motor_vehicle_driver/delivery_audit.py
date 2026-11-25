"""Independent original-attempt audit for the conditional right-lane cases.

Software checks bind original bytes and complete synchronized video. They do
not decide legal impediment or necessity, or establish physical visibility.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from finalize_follower import finalize
from reviewed_scene import ASSIGNMENT, VARIANTS, _linked, plan

CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ref(root: Path, ref: dict) -> Path:
    return _linked(root, ref)


def _probe(path: Path) -> dict:
    command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_frames",
               "-show_entries", "stream=nb_read_frames,r_frame_rate,width,height",
               "-of", "json", str(path)]
    result = subprocess.run(command, capture_output=True, text=True, check=True, timeout=120)
    streams = json.loads(result.stdout).get("streams", [])
    if len(streams) != 1:
        raise ValueError("one original video stream required")
    return streams[0]


def audit(root: Path, receipt: dict, probe=_probe) -> dict:
    root = Path(root).resolve()
    case_id = receipt.get("case_id", "")
    if case_id not in {ASSIGNMENT + "__" + suffix for suffix in VARIANTS}:
        raise ValueError("exact assigned case required")
    if (receipt.get("source_kind") != "original_native_attempt" or
            receipt.get("diagnostic_fixture") is True or
            receipt.get("native_process_exit_code") != 0 or
            receipt.get("owner_released") is not True or
            not receipt.get("attempt_id") or not receipt.get("recording_id")):
        raise ValueError("successful released original Native attempt required")
    site_ref = receipt.get("site_ref")
    scene = plan(root, site_ref, case_id)
    seal_ref = receipt.get("capture_seal_ref")
    seal_path = _ref(root, seal_ref)
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if (seal.get("source_kind") != "original_native_capture_seal" or
            seal.get("case_id") != case_id or
            seal.get("attempt_id") != receipt["attempt_id"] or
            seal.get("recording_id") != receipt["recording_id"]):
        raise ValueError("sealed original Native attempt identity differs")
    refs = [site_ref, receipt.get("frame_map_ref"), receipt.get("trace_ref"),
            receipt.get("relation_ref")] + list(receipt.get("video_refs", {}).values())
    for ref in refs:
        if not isinstance(ref, dict) or seal.get("sources", {}).get(ref.get("path")) != ref.get("sha256"):
            raise ValueError("sealed original source inventory differs")
    frame_path = _ref(root, receipt.get("frame_map_ref"))
    frame_map = json.loads(frame_path.read_text(encoding="utf-8"))
    rows = frame_map.get("frames")
    if (frame_map.get("source_kind") != "original_native_frame_map" or
            frame_map.get("case_id") != case_id or not isinstance(rows, list) or
            len(rows) != 900 or [r.get("frame") for r in rows] != list(range(900))):
        raise ValueError("complete original 900-frame map required")
    native = [r.get("native_frame") for r in rows]
    if any(type(v) is not int for v in native) or any(b <= a for a, b in zip(native, native[1:])):
        raise ValueError("original Native frame IDs not increasing")
    for i, row in enumerate(rows):
        if row.get("time_s") != i / 20 or set(row.get("camera_frames", {})) != set(CAMERAS):
            raise ValueError("original 20 Hz four-camera frame join missing")
        if any(row["camera_frames"][name] != native[i] for name in CAMERAS):
            raise ValueError("four-camera original Native frame mismatch")
    videos = receipt.get("video_refs")
    if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
        raise ValueError("four original camera videos required")
    video_hashes = {}
    for name in CAMERAS:
        path = _ref(root, videos[name])
        stream = probe(path)
        if stream.get("nb_read_frames") != "900" or stream.get("r_frame_rate") != "20/1":
            raise ValueError("original camera full decode or 20 Hz failed: " + name)
        if int(stream.get("width", 0)) < 640 or int(stream.get("height", 0)) < 360:
            raise ValueError("original camera resolution below review floor")
        video_hashes[name] = _sha(path)
    trace_path = _ref(root, receipt.get("trace_ref"))
    relation_path = _ref(root, receipt.get("relation_ref"))
    if json.loads(trace_path.read_text(encoding="utf-8")).get("diagnostic_fixture") is True:
        raise ValueError("diagnostic motion source cannot be original delivery")
    observation = finalize(trace_path, receipt["trace_ref"]["sha256"],
                           relation_path, receipt["relation_ref"]["sha256"], case_id)
    measured = observation["observations"]
    if len(measured) != 900:
        raise ValueError("original 900-frame measurement required")
    requested_right = scene["actors"][0]["lane_id"] == scene["rightmost_lane_id"]
    requested_follower = scene["requested_immediate_follower"]
    if (any(row["ego_in_extreme_right_lane"] != requested_right for row in measured) or
            any(row["follower_immediately_behind_in_ego_lane"] != requested_follower for row in measured)):
        raise ValueError("realized lane or follower differs from requested construction")
    if scene["requested_immediate_follower"] and not any(
            row["follower_closing_speed_mps"] > 0 for row in measured):
        raise ValueError("original following traffic did not close on ego")
    if scene.get("requested_passing_slower_vehicle") and not any(
            row["passing_slower_vehicle_observed"] for row in measured):
        raise ValueError("original requested pass not observed")
    return {"format": "c147344-original-attempt-audit-v1", "case_id": case_id,
            "attempt_id": receipt["attempt_id"], "recording_id": receipt["recording_id"],
            "source_kind": "original_native_attempt", "site_sha256": site_ref["sha256"],
            "capture_seal_sha256": _sha(seal_path),
            "map_sha256": scene["map_sha256"], "frame_map_sha256": _sha(frame_path),
            "trace_sha256": _sha(trace_path), "relation_sha256": _sha(relation_path),
            "video_sha256": video_hashes, "frames_checked": 900,
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "original_lane_and_follower_readback"],
            "physical_completion": "requires independent local visual and motion review",
            "legal_impediment_and_pass_necessity": "unresolved"}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.authority_root.resolve()):
        raise ValueError("fresh audit output outside original source root required")
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    result = audit(args.authority_root, receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
