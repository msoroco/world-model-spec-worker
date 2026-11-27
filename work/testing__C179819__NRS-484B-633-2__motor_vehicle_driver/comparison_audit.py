"""Audit exact bridge comparison isolation from current source-sealed cases."""

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SPEED = "requested_speed_delta_from_declared_maximum_mph"
SIGN = "requested_sign_offset_ft"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, *, corrupt=False):
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    comparisons = {item["comparison_id"]: item for item in plan["comparisons"]}
    if comparison_id not in comparisons:
        raise ValueError("exact selected comparison required")
    comparison = comparisons[comparison_id]
    planned = {item["case_id"]: item for item in plan["cases"]}
    entries = {item["case_id"]: item for item in manifest["cases"]}
    if set(comparison["case_ids"]) - set(planned) or set(comparison["case_ids"]) - set(entries):
        raise ValueError("comparison omits selected exact cases")
    axis = SIGN if "sign_station" in comparison_id else SPEED
    expected = [99, 100, 101] if axis == SIGN else [-5, 0, 5] if len(comparison["case_ids"]) == 3 else [0, 5]
    fixed = None
    values = []
    seals = []
    for index, case_id in enumerate(comparison["case_ids"]):
        case = planned[case_id]
        entry = entries[case_id]
        if case.get("target_law_id") != plan["law_id"]:
            raise ValueError("comparison law changed")
        construction = ROOT / entry["construction"]
        receipt_path = ROOT / entry["compatibility"]["receipt"]
        delivery_path = ROOT / entry["delivery_acceptance"]["test_log"]
        if (sha(construction) != entry["construction_sha256"] or
                sha(receipt_path) != entry["compatibility"]["sha256"] or
                not json.loads(receipt_path.read_text()).get("passed") or
                sha(delivery_path) != entry["delivery_acceptance"]["test_log_sha256"]):
            raise ValueError("comparison member proof changed")
        value = case[axis]
        if corrupt and index == 1:
            value += 2
        values.append(value)
        conditions = {key: case[key] for key in (SIGN, SPEED, "structure_kind_request", "travel_direction_request") if key != axis}
        if fixed is None:
            fixed = conditions
        elif conditions != fixed:
            raise ValueError("comparison changed a non-axis condition")
        seals.append({"case_id": case_id, "construction_sha256": sha(construction),
                      "compatibility_sha256": sha(receipt_path),
                      "delivery_protocol_sha256": sha(delivery_path)})
    if values != expected:
        raise ValueError("comparison engineering probe spacing changed")
    return {"comparison_id": comparison_id, "axis": axis, "setpoints": values,
            "source_seals": seals, "cpu_protocol_passed": True,
            "original_delivery_claimed": False, "legal_verdict": "unresolved"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, corrupt=args.negative), sort_keys=True))


if __name__ == "__main__":
    main()
