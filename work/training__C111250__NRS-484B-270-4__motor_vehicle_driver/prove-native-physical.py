"""Source-bound synthetic motion outcomes; never original CARLA acceptance."""
import argparse
import hashlib
import json
from pathlib import Path

from native.facility import body_overlap

HERE = Path(__file__).resolve().parent
EVENTS = ["capture_finished", "encoders_closed", "restoration_verified",
          "native_exit", "owner_released", "saved_processing_started"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind):
    if case_id not in [HERE.name + "__controlled_1", HERE.name + "__controlled_2"]:
        raise ValueError("Wrong exact case")
    suffix = case_id.rsplit("__", 1)[1]
    construction = HERE / ("draft-native-" + suffix + "-construction.json")
    base = {"case_id": case_id, "construction_sha256": sha(construction),
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "original_native_motion_verified": False, "accepted": False,
            "legal_verdict_claimed": False}
    if kind == "lifecycle":
        return dict(base, events=EVENTS, exit_code=0)
    if kind not in ("complete_motion", "incomplete_motion", "missing_evidence"):
        raise ValueError("Unknown outcome")
    source = HERE / ("native-diagnostic-" + suffix + "-sources/body-history.jsonl")
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    if len(rows) != 600 or [row["native_frame"] for row in rows] != list(range(600)):
        raise ValueError("Diagnostic source frame continuity differs")
    if kind == "missing_evidence":
        observed = []
    elif kind == "incomplete_motion":
        observed = rows[:100]
    else:
        observed = rows
    overlap = sum(body_overlap(row)["cycle_intersection_body_overlap_m2"] > 0
                  for row in observed)
    inside = sum(body_overlap(row)["inside_intersection"] for row in observed)
    joined = all(row["native_frame"] == index and
                 abs(row["time_s"] - index / 20) < 1e-6 and
                 row["source_kind"] == "synthetic_cpu_diagnostic"
                 for index, row in enumerate(observed))
    complete = (len(observed) == 600 and joined and inside > 0 and
                overlap >= (20 if suffix == "controlled_1" else 80) and
                all(row["speed_mps"] > 0 for row in observed))
    status = "unverified" if not observed else "met" if complete else "not_met"
    return dict(base,
                physical_checks={"maneuver": {"status": status,
                    "method": "Joined 20 Hz body/velocity rows; intersection and bicycle-lane body overlap",
                    "sources": [str(source.relative_to(HERE))] if observed else
                               ["missing body-history diagnostic rows"]}},
                maneuver_completed=complete,
                realized_observables={"frames": len(observed), "inside_intersection_frames": inside,
                                      "cycle_lane_intersection_overlap_frames": overlap,
                                      "joined": joined} if observed else {},
                retained_source_sha256={"body-history.jsonl": sha(source)} if observed else {})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--kind", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": args.case, "kind": args.kind,
                      "status": result.get("physical_checks", {}).get("maneuver", {}).get("status", "lifecycle"),
                      "original_native_motion_verified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
