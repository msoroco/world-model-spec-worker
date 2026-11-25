"""Exercise each materialized exact-case finalizer with source-shaped CPU packets.

The generated frames are diagnostic software fixtures and never original evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from reviewed_scene import ASSIGNMENT, VARIANTS


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")


def run(bundle: Path, output: Path, case_id: str) -> dict:
    if case_id not in {ASSIGNMENT + "__" + name for name in VARIANTS}:
        raise ValueError("exact case ID required")
    if output.exists():
        raise ValueError("fresh diagnostic output required")
    output.mkdir(parents=True)
    config = json.loads((bundle / "config.json").read_text(encoding="utf-8"))
    if config.get("selected_case_id") != case_id or config.get("diagnostic_only") is not True:
        raise ValueError("materialized diagnostic case mismatch")
    suffix = case_id.removeprefix(ASSIGNMENT + "__")
    right = suffix == "slow_right_follower"
    immediate = suffix != "slow_middle_no_immediate_follower"
    passing = suffix == "slow_middle_passing"
    ego_lane = "-1" if right else "-2"
    follower_lane = ego_lane if immediate else "-1"
    trace = {"assignment_id": ASSIGNMENT, "case_id": case_id,
             "original_trace_id": "synthetic-fixture-" + suffix,
             "diagnostic_fixture": True,
             "frames": [{"frame": i, "time_s": i / 20,
                         "ego_speed_mps": 5.0, "follower_gap_m": 20.0 - i * 0.001,
                         "follower_speed_mps": 8.0,
                         "ego_lane_id": ego_lane, "rightmost_same_direction_lane_id": "-1",
                         "follower_actor_id": "fixture-follower", "follower_lane_id": follower_lane,
                         "passing_slower_vehicle_observed": passing and i >= 450,
                         "same_direction_marked_lane_count": 2}
                        for i in range(900)]}
    relation = {"case_id": case_id, "source_kind": "original_native_relation",
                "relation_basis_source": "synthetic CPU ordering fixture only",
                "samples": [{"frame": i, "time_s": i / 20,
                             "follower_actor_id": "fixture-follower",
                             "immediately_behind": immediate} for i in range(900)]}
    trace_path, relation_path = output / "trace.json", output / "relation.json"
    write(trace_path, trace)
    write(relation_path, relation)
    code = ("import json,sys;from finalize_follower import finalize;"
            "r=finalize(sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4],sys.argv[5]);"
            "print(json.dumps({'case_id':r['case_id'],'frames':r['original_frame_count'],"
            "'observations':len(r['observations'])}))")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(bundle) + os.pathsep + env.get("PYTHONPATH", "")
    command = [sys.executable, "-c", code, str(trace_path), sha(trace_path),
               str(relation_path), sha(relation_path), case_id]
    positive = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
    if positive.returncode:
        raise ValueError("diagnostic exact-case positive failed: " + positive.stderr[-1000:])
    measured = json.loads(positive.stdout)
    if measured != {"case_id": case_id, "frames": 900, "observations": 900}:
        raise ValueError("diagnostic selected finalizer returned wrong case or frame count")
    relation_bytes = relation_path.read_bytes()
    relation_path.unlink()
    negative = subprocess.run(command, env=env, capture_output=True, text=True, timeout=60)
    if negative.returncode == 0 or "FileNotFoundError" not in negative.stderr:
        raise ValueError("missing relation source was not rejected")
    relation_path.write_bytes(relation_bytes)
    return {"format": "c147344-diagnostic-case-compatibility-v1", "case_id": case_id,
            "construction_sha256": sha(bundle / "construction.json"),
            "source_kind": "synthetic_software_fixture", "positive_exit_code": 0,
            "positive_frames": 900, "negative_exit_code": negative.returncode,
            "negative_missing_source": "relation.json", "negative_expected_error": "FileNotFoundError",
            "delivery_ready": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", required=True)
    args = parser.parse_args()
    receipt = run(args.bundle, args.output, args.case)
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
