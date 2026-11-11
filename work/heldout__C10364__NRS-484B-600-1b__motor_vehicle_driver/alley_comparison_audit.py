"""Independent measured-source comparison for the C10364 alley sweep."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


ASSIGNMENT = "heldout__C10364__NRS-484B-600-1b__motor_vehicle_driver"


def audit(paths, interest):
    if interest not in ("person", "property") or len(paths) != 3:
        raise ValueError("Comparison requires three cases of one protected interest")
    reports = []
    for path in paths:
        path = Path(path)
        raw = path.read_bytes()
        report = json.loads(raw)
        reports.append((report, sha256(raw).hexdigest()))
    expected = [f"{ASSIGNMENT}__{interest}_{speed}mps" for speed in (3, 5, 7)]
    case_ids = [report.get("case_id") for report, _ in reports]
    if case_ids != expected:
        raise ValueError("Comparison case identities or order differ")
    shared = [report.get("fixed_conditions") for report, _ in reports]
    if any(not isinstance(value, dict) or value != shared[0] for value in shared):
        raise ValueError("Comparison fixed conditions differ")
    for report, _ in reports:
        sources = report.get("source_sha256")
        if (not isinstance(sources, dict)
                or set(sources) != {"participant_footprints.jsonl", "ego_motion.jsonl",
                                        "trace.jsonl", "video_frames.jsonl"}
                or any(not isinstance(value, str) or len(value) != 64 for value in sources.values())):
            raise ValueError("Comparison lacks required original source hashes")
        if report.get("physical_acceptance_claimed") or report.get("legal_acceptance_claimed"):
            raise ValueError("Comparison source claims unsupported acceptance")
    speeds = [report.get("maximum_observed_speed_mps") for report, _ in reports]
    if any(type(value) not in (int, float) or value < 0 for value in speeds):
        raise ValueError("Comparison lacks measured original-frame speed")
    gap_key = "minimum_pedestrian_gap_m" if interest == "person" else "minimum_property_gap_m"
    gaps = [report.get(gap_key) for report, _ in reports]
    if any(type(value) not in (int, float) or value < 0 for value in gaps):
        raise ValueError("Comparison lacks measured protected-interest gap")
    return {"format": "worker-alley-comparison-audit", "comparison_id": f"{interest}_speed_sweep",
            "case_ids": case_ids, "report_sha256": [digest for _, digest in reports],
            "fixed_conditions": shared[0], "measured_speeds_mps": speeds,
            "measured_gaps_m": gaps,
            "speed_order_realized": speeds[0] < speeds[1] < speeds[2],
            "comparison_complete": speeds[0] < speeds[1] < speeds[2],
            "legal_acceptance_claimed": False, "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interest", choices=("person", "property"), required=True)
    parser.add_argument("--reports", nargs=3, required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain prior comparison audit; use a fresh output")
    output.write_text(json.dumps(audit(args.reports, args.interest), indent=2) + "\n")


if __name__ == "__main__":
    main()
