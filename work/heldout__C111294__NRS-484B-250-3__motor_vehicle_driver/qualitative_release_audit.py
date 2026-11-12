"""Audit measured release-delay contrast in original intersection body histories.

Controller setpoints are construction inputs. This audit requires a distinct
observed entry frame at each point before calling the set a measured sweep.
It makes no legal approximation or right-of-way judgment.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from ending_road_measurement import measure


def _bytes(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError("Missing original sweep source: " + name)
    return path.read_bytes()


def audit(attempts):
    if len(attempts) != 3:
        raise ValueError("Three exact release-delay attempts required")
    points = []
    fixed_topology = None
    fixed_other = None
    fixed_initial_subject = None
    for attempt in attempts:
        root = Path(attempt)
        config = json.loads(_bytes(root, "config.json"))
        case_id = config.get("selected_case_id", "")
        if not case_id.endswith("__yield_release_delay-0000") and not case_id.endswith("__yield_release_delay-0001") and not case_id.endswith("__yield_release_delay-0002"):
            raise ValueError("Unexpected exact release-delay case")
        topology_raw = _bytes(root, "intersection_topology.json")
        rows_raw = _bytes(root, "intersection_participants.jsonl")
        rows = [json.loads(line) for line in rows_raw.splitlines() if line.strip()]
        if not rows:
            raise ValueError("Empty original participant history")
        topology_hash = sha256(topology_raw).hexdigest()
        if fixed_topology is None:
            fixed_topology = topology_hash
        elif topology_hash != fixed_topology:
            raise ValueError("Release sweep changed fixed lane topology")
        other = [(row.get("frame"), row.get("time_s"), row.get("other_id"), row.get("other_corners")) for row in rows]
        if fixed_other is None:
            fixed_other = other
            fixed_initial_subject = (rows[0].get("subject_id"), rows[0].get("subject_corners"))
        elif other != fixed_other or (rows[0].get("subject_id"), rows[0].get("subject_corners")) != fixed_initial_subject:
            raise ValueError("Release sweep changed fixed actors or initial subject setup")
        observation = measure(root / "intersection_topology.json", root / "intersection_participants.jsonl")
        points.append({
            "case_id": case_id,
            "setpoint_frames": config.get("release_delay_frames"),
            "subject_entry_frame": observation["subject_entry_frame"],
            "entry_delta_s": observation["entry_delta_s"],
            "participant_source_sha256": sha256(rows_raw).hexdigest(),
        })
    points.sort(key=lambda point: point["setpoint_frames"])
    if [point["setpoint_frames"] for point in points] != [0, 80, 160]:
        raise ValueError("Release sweep setpoints differ from planned finite points")
    frames = [point["subject_entry_frame"] for point in points]
    if not frames[0] < frames[1] < frames[2]:
        raise ValueError("Release sweep lacks measured entry-timing contrast in original bodies")
    return {
        "format": "worker-ending-road-qualitative-release-audit",
        "fixed_topology_sha256": fixed_topology,
        "points": points,
        "legal_threshold_claimed": False,
        "physical_realization_claimed": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", action="append", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
