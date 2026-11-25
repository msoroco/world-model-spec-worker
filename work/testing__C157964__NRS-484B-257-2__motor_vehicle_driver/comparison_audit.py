"""Independent source-bound comparison of the exact officer branches.

The result describes a recorded contrast. It does not decide the statute.
"""

import argparse
import hashlib
import json
from pathlib import Path

from officer_direction import PREFIX


PAIRS = {
    "officer_control_exception": (PREFIX + "officer_controls_go", PREFIX + "officer_present_inactive"),
    "officer_direction": (PREFIX + "officer_controls_go", PREFIX + "officer_controls_hold"),
}
FIXED = ("native_map_id", "intersection_id", "junction_source", "ego_route_source",
         "sign_inventory_source", "other_entrance_source", "highway_status_source",
         "non_through_highway", "ego_entrance_device", "other_entrance_device",
         "intersection_polygon_xy_m")


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path):
    if not path.is_file():
        raise ValueError("Missing comparison source: " + str(path))
    return json.loads(path.read_text())


def _attempt(root, expected):
    root = Path(root)
    report = _read(root / "analysis.json")
    if report.get("format") != "worker-c157964-subsection-2-saved-analysis" or report.get("case_id") != expected:
        raise ValueError("Comparison exact case ID differs")
    if report.get("legal_conclusion") != "unresolved" or report.get("physical_acceptance_claimed") is not False:
        raise ValueError("Comparison cannot pre-decide legal or physical outcome")
    context = _read(root / "officer_context.json")
    history_path = root / "officer_history.jsonl"
    if context.get("case_id") != expected or not history_path.is_file():
        raise ValueError("Missing exact original officer context/history")
    hashes = report.get("source_sha256", {})
    if hashes.get("officer_context.json") != _sha(root / "officer_context.json") or hashes.get("officer_history.jsonl") != _sha(history_path):
        raise ValueError("Comparison original source hash changed")
    rows = [json.loads(line) for line in history_path.read_text().splitlines() if line.strip()]
    observed = report.get("source_report", {})
    samples = observed.get("samples")
    if not rows or not isinstance(samples, list) or len(rows) != len(samples):
        raise ValueError("Comparison original frame interval incomplete")
    for row, sample in zip(rows, samples):
        if (row.get("frame") != sample.get("frame") or row.get("time_s") != sample.get("time_s")
                or row.get("officer_direction_observed") != sample.get("direction")
                or row.get("traffic_control_observed") is not sample.get("traffic_control_observed")
                or not row.get("direction_frame_source") or not row.get("other_frame_source")):
            raise ValueError("Comparison saved observation differs from original frame")
    return context, observed, hashes


def audit(comparison_id, first_root, second_root):
    if comparison_id not in PAIRS:
        raise ValueError("Unknown exact comparison")
    first_id, second_id = PAIRS[comparison_id]
    first_context, first, first_hashes = _attempt(first_root, first_id)
    second_context, second, second_hashes = _attempt(second_root, second_id)
    if any(first_context.get(key) != second_context.get(key) for key in FIXED):
        raise ValueError("Comparison fixed site and sign context differs")
    left = first.get("first_ego_entry")
    right = second.get("first_ego_entry") or second.get("first_hold_observation")
    if not left or not right:
        raise ValueError("Comparison lacks source-observed entry or hold")
    if comparison_id == "officer_control_exception":
        if (left.get("traffic_control_observed"), right.get("traffic_control_observed")) != (True, False):
            raise ValueError("Original officer-control contrast missing")
        if (left.get("officer_direction_observed"), right.get("officer_direction_observed")) != ("go", "none"):
            raise ValueError("Original go versus inactive direction contrast missing")
    else:
        if (left.get("traffic_control_observed"), right.get("traffic_control_observed")) != (True, True):
            raise ValueError("Direction comparison lacks active control")
        if (left.get("officer_direction_observed"), right.get("officer_direction_observed")) != ("go", "stop"):
            raise ValueError("Original go versus hold direction contrast missing")
    return {"format": "worker-c157964-subsection-2-comparison-audit",
            "comparison_id": comparison_id, "case_ids": [first_id, second_id],
            "fixed_context": {key: first_context[key] for key in FIXED},
            "source_hashes": {"first": first_hashes, "second": second_hashes},
            "observed": {"first": left, "second": right},
            "comparison_passed": True, "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", choices=sorted(PAIRS), required=True)
    parser.add_argument("--first", type=Path, required=True)
    parser.add_argument("--second", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.comparison, args.first, args.second)
    args.output.write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
