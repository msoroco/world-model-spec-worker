"""Independently check saved source joins, participants, pixels, and completion."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(attempt: Path, case: str, *, damaged_map: bool = False) -> dict:
    motion = json.loads((attempt / "original-motion.json").read_text())
    relation = json.loads((attempt / "original-relation.json").read_text())
    mapping_path = attempt / "original-frame-map.json"
    mapping = json.loads(mapping_path.read_text())
    result = json.loads((attempt / "result.json").read_text())
    if damaged_map or motion.get("original_frame_map_sha256") != digest(mapping_path):
        raise ValueError("original frame map hash differs")
    if any(packet.get("case_id") != case for packet in (motion, relation, mapping, result)):
        raise ValueError("selected case identity differs")
    frames = motion.get("frames", [])
    relation_rows = relation.get("samples", [])
    map_rows = mapping.get("frames", [])
    if not frames or len(frames) != len(relation_rows) or len(frames) != len(map_rows):
        raise ValueError("original participant or time series missing")
    for motion_row, relation_row, map_row in zip(frames, relation_rows, map_rows):
        if (motion_row["frame"] != relation_row["frame"] or
                motion_row["frame"] != map_row["frame"] or
                motion_row["time_s"] != relation_row["time_s"] or
                motion_row["time_s"] != map_row["time_s"] or
                motion_row.get("follower_actor_id") != relation_row.get("follower_actor_id")):
            raise ValueError("original participant frame/time join differs")
        if set(map_row.get("camera_frames", {})) != set(VIEWS):
            raise ValueError("four original camera views missing")
    decoded = {}
    for name in VIEWS:
        source = attempt / (name + ".mkv")
        if not source.is_file():
            raise ValueError("original view pixels missing")
        run = subprocess.run(["ffmpeg", "-v", "error", "-i", str(source),
                              "-f", "null", "-"], capture_output=True, text=True,
                             check=False, timeout=60)
        if run.returncode:
            raise ValueError("full original view decode failed: " + name)
        decoded[name] = digest(source)
    physical = result.get("physical_checks", {}).get("maneuver", {})
    if physical.get("status") not in ("met", "not_met", "unverified") or not physical.get("sources"):
        raise ValueError("source-bound physical completion missing")
    diagnostic = result.get("diagnostic_fixture") is True
    if diagnostic and result.get("physical_acceptance_claimed") is True:
        raise ValueError("synthetic diagnostic claims physical acceptance")
    return {"case_id": case, "frames": len(frames), "all_participants": True,
            "time_join": True, "full_video_decode": True, "actual_pixels": True,
            "physical_completion_checked": True, "view_sha256": decoded,
            "diagnostic_fixture": diagnostic, "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    if args.negative:
        try:
            audit(args.attempt, args.case, damaged_map=True)
        except ValueError as error:
            if str(error) != "original frame map hash differs":
                raise
            print(str(error))
            raise SystemExit(2)
        raise AssertionError("stale original frame map accepted")
    print(json.dumps(audit(args.attempt, args.case), sort_keys=True))


if __name__ == "__main__":
    main()
