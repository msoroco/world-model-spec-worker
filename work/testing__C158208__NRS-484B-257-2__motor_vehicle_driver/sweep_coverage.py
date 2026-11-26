"""Classify source-audited original yield measurements against training ranges.

This is physical coverage bookkeeping. Training endpoints are not legal cutoffs.
The command refuses diagnostic attempts through the independent delivery audit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from selected_delivery import audit as audit_delivery

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "inputs" / HERE.name / "judgment_ranges.json"
ASSIGNMENT = HERE.name
OBSERVABLES = {
    ("counterpart_center_station", "first"): "counterpart_center_station_first_m",
    ("ego_speed", "min"): "ego_speed_min_peak_to_stop_reference_mps",
    ("ego_speed", "mean"): "ego_speed_mean_full_body_overlap_to_clear_mps",
}


def classify(original_values: dict[str, dict]) -> dict:
    """Use only audited, original, nontransient frozen-window values."""
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source = json.loads(SOURCE.read_text())
    rows = [row for row in source["full-test"]["ranges"]
            if json.loads(row["key"])[0] == "NRS-484B-257-2"]
    if len(rows) != 9:
        raise ValueError("frozen 257(2) range inventory changed")
    output = []
    for index, row in enumerate(rows):
        key = json.loads(row["key"])
        observable = OBSERVABLES.get((key[3], key[5]["statistic"]))
        if observable is None:
            raise ValueError("frozen judgment observable mapping missing")
        low, high = row["minimum"], row["maximum"]
        bins = {name: [] for name in ("below", "inside", "above")}
        for case_id, measured in original_values.items():
            if not case_id.startswith(ASSIGNMENT + "__"):
                raise ValueError("measurement case outside exact assignment")
            value = measured.get(observable)
            if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                raise ValueError("missing finite original frozen-window observable: " + observable)
            bucket = "below" if value < low else "above" if value > high else "inside" if low < value < high else None
            if bucket:
                bins[bucket].append({"case_id": case_id, "value": value})
        output.append({"range_index": index, "judgment_key": row["key"],
                       "observable": observable, "training_minimum": low,
                       "training_maximum": high, "witnesses": bins,
                       "strict_interior_possible": low < high,
                       "missing": [name for name, values in bins.items()
                                   if not values and (name != "inside" or low < high)]})
    return {"format": "c158208-original-judgment-sweep-coverage-v1",
            "assignment_id": ASSIGNMENT, "training_source_sha256": source_hash,
            "ranges": output, "legal_conclusion": None,
            "physical_acceptance_claimed": False}


def audited_attempts(paths: list[Path]) -> dict:
    values = {}
    for path in paths:
        attempt = Path(path)
        result = json.loads((attempt / "result.json").read_text())
        case_id = result.get("case_id")
        if case_id in values or not isinstance(case_id, str):
            raise ValueError("duplicate or missing exact case")
        audit_delivery(attempt, case_id, False)
        if result.get("diagnostic_fixture") is not False:
            raise ValueError("original source required for sweep coverage")
        values[case_id] = result.get("realized_observables", {})
    if not values:
        raise ValueError("original audited attempts required")
    return classify(values)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("attempt", type=Path, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("sweep coverage output already exists")
    result = audited_attempts(args.attempt)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"ranges": len(result["ranges"]),
                      "missing": {row["range_index"]: row["missing"] for row in result["ranges"]}},
                     sort_keys=True))
