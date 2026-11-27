"""Independent CPU comparison of original-source measurement summaries.

The caller supplies the exact case plan and two measured records. The records
must retain hashes of sealed Native and camera sources. Fixture tests exercise
rejection behavior only; they are never physical acceptance receipts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


FIXED = (
    "law_id", "cell_id", "actor", "governing_signal_id", "rate_hz",
    "camera_profile", "road_geometry_sha256", "signal_program_sha256",
)


def audit(plan: dict, comparison_id: str, records: list[dict]) -> dict:
    comparison = next((x for x in plan["comparisons"] if x["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("Unknown exact comparison")
    if len(records) != 2 or {x.get("case_id") for x in records} != set(comparison["case_ids"]):
        raise ValueError("Exact comparison case identities differ")
    records = sorted(records, key=lambda x: comparison["case_ids"].index(x["case_id"]))
    for record in records:
        if record.get("source_kind") != "native_observed":
            raise ValueError("Comparison lacks original Native source")
        for key in ("native_source_sha256", "camera_source_sha256", "sealed_result_sha256"):
            if not isinstance(record.get(key), str) or len(record[key]) != 64 or not all(c in "0123456789abcdef" for c in record[key]):
                raise ValueError("Comparison lacks source binding: " + key)
        if record.get("law_id") != plan["law_id"] or record.get("cell_id") != plan["cell_id"] or record.get("actor") != plan["actor"]:
            raise ValueError("Comparison scope differs")
    first, second = records
    for key in FIXED:
        if first.get(key) is None or first[key] != second.get(key):
            raise ValueError("Fixed comparison condition differs: " + key)
    for variable in comparison["deliberate_differences"]:
        if variable not in first.get("measurements", {}) or variable not in second.get("measurements", {}):
            raise ValueError("Missing comparison measurement: " + variable)
        if first["measurements"][variable] == second["measurements"][variable]:
            raise ValueError("Declared comparison difference was not observed: " + variable)
    return {
        "comparison_id": comparison_id,
        "case_ids": comparison["case_ids"],
        "fixed_conditions_checked": list(FIXED),
        "deliberate_differences_checked": comparison["deliberate_differences"],
        "source_kind": "native_observed",
        "physical_or_legal_acceptance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--first", required=True)
    parser.add_argument("--second", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    plan = json.loads(Path(args.plan).read_text())
    records = [json.loads(Path(name).read_text()) for name in (args.first, args.second)]
    result = audit(plan, args.comparison, records)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
