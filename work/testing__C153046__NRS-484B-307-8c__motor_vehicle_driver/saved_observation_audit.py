"""Replay source-cited observations against each saved Native frame.

This is an engineering integrity check. Zone overlap is a conservative wait
request, not a finding about statutory right-of-way or physical visibility.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from build_case_plan import AID, KINDS
from native_observation import from_frame, plan


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(site: Path, trace: Path, case_id: str, *, expected_frames: int = 600) -> dict:
    if not case_id.startswith(AID + "__") or case_id[len(AID) + 2:] not in KINDS:
        raise ValueError("unknown exact case")
    site, trace = Path(site), Path(trace)
    scene, observation_plan = plan(site, case_id[len(AID) + 2:])
    rows = [json.loads(line) for line in trace.read_text().splitlines() if line.strip()]
    if len(rows) != expected_frames or expected_frames < 2:
        raise ValueError("original frame count differs from planned window")
    previous_frame = previous_time = None
    counts = {"pedestrian_conflict": 0, "traffic_conflict": 0, "junction_exited": 0}
    for index, row in enumerate(rows):
        frame = row.get("native_frame")
        if (row.get("case_id") != case_id or
                row.get("source_packet_sha256") != scene["source_packet_sha256"] or
                row.get("selected_approach_lane_id") != scene["selected_approach_lane_id"] or
                row.get("original_sample_claim") is not True or not isinstance(frame, dict)):
            raise ValueError("original frame source or case join differs")
        number = frame.get("frame")
        time_s = frame.get("time_s")
        if (type(number) is not int or (previous_frame is not None and number != previous_frame + 1) or
                type(time_s) not in (int, float) or not math.isfinite(time_s) or
                (previous_time is not None and time_s <= previous_time)):
            raise ValueError("original frame/time sequence differs")
        if row.get("frame") != number:
            raise ValueError("outer frame ID differs from original")
        observation = from_frame(frame, scene, observation_plan)
        checks = {
            "time_s": observation.time_s,
            "distance_to_stop_boundary_m": observation.distance_to_stop_boundary_m,
            "speed_m_s": observation.speed_m_s,
            "signal": observation.signal,
            "pedestrian_conflict": observation.pedestrian_conflict,
            "traffic_conflict": observation.traffic_conflict,
            "junction_exited": observation.junction_exited,
        }
        for name, actual in checks.items():
            claimed = row.get(name)
            if type(actual) is bool:
                same = type(claimed) is bool and claimed == actual
            elif type(actual) is float:
                same = type(claimed) in (int, float) and math.isfinite(claimed) and abs(claimed - actual) <= 1e-6
            else:
                same = claimed == actual
            if not same:
                raise ValueError(f"original observation differs at frame {index}: {name}")
        for name in counts:
            counts[name] += int(checks[name])
        previous_frame, previous_time = number, time_s
    return {"format": "c153046-saved-observation-audit", "case_id": case_id,
            "site_packet_sha256": sha(site), "trace_sha256": sha(trace),
            "first_frame": rows[0]["frame"], "last_frame": rows[-1]["frame"],
            "frames_checked": len(rows), "source_hashes": scene["source_hashes"],
            "observation_counts": counts, "passed": True,
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain previous audit receipt")
    receipt = audit(args.site, args.trace, args.case)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["case_id"], receipt["frames_checked"], "observations verified")


if __name__ == "__main__":
    main()
