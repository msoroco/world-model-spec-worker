"""Independent comparison for staged crossing-speed cases after original capture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from selected_delivery import audit as audit_delivery
from sweep_coverage import classify

HERE = Path(__file__).resolve().parent


def compare(records: list[tuple[dict, dict]]) -> dict:
    extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
    expected = {row["case_id"]: row for row in extension["cases"]}
    if {config.get("selected_case_id") for config, _ in records} != set(expected) or len(records) != 3:
        raise ValueError("exact three speed sweep cases required")
    fixed = []
    values = {}
    for config, result in records:
        case_id = config["selected_case_id"]
        variables = config["case"]["draft_variables"]
        if variables != expected[case_id]["draft_variables"] or result.get("case_id") != case_id:
            raise ValueError("selected speed sweep construction identity differs")
        hold = dict(variables)
        hold.pop("requested_ego_crossing_speed_mps")
        fixed.append(hold)
        values[case_id] = result.get("realized_observables", {})
    if not all(row == fixed[0] for row in fixed[1:]):
        raise ValueError("speed sweep fixed conditions differ")
    coverage = classify(values)
    for index in (2, 5, 8):
        row = coverage["ranges"][index]
        for bin_name in ("below", "inside", "above"):
            case_id = next(case for case, spec in expected.items()
                           if spec["target_bin"] == bin_name)
            if not any(witness["case_id"] == case_id for witness in row["witnesses"][bin_name]):
                raise ValueError("realized crossing speed missed planned " + bin_name + " bin")
    return {"format": "c158190-original-speed-sweep-comparison-v1",
            "case_ids": sorted(expected), "range_indices": [2, 5, 8],
            "training_source_sha256": coverage["training_source_sha256"],
            "fixed_conditions_checked": True, "realized_bins_checked": True,
            "legal_conclusion": None, "physical_acceptance_claimed": False}


def audit_attempts(paths: list[Path]) -> dict:
    records = []
    for path in paths:
        attempt = Path(path)
        config = json.loads((attempt / "config.json").read_text())
        result = json.loads((attempt / "result.json").read_text())
        audit_delivery(attempt, config["selected_case_id"], False)
        if result.get("diagnostic_fixture") is not False:
            raise ValueError("original speed comparison rejects diagnostic attempt")
        records.append((config, result))
    return compare(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path, nargs=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("speed comparison output already exists")
    result = audit_attempts(args.attempt)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, sort_keys=True))
