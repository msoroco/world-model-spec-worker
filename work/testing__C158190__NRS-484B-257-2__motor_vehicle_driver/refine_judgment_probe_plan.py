"""Bind feasible planning targets to the frozen 257(2) training ranges.

Targets guide later physical acquisition. They are neither observed values nor
legal boundaries. Equal training endpoints have no strictly interior real value.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / "inputs" / HERE.name / "judgment_ranges.json"
PLAN = HERE / "judgment-probe-plan.json"


def refine() -> dict:
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    source = json.loads(SOURCE.read_text())
    plan = json.loads(PLAN.read_text())
    ranges = list(enumerate(row for row in source["full-test"]["ranges"]
                            if json.loads(row["key"])[0] == "NRS-484B-257-2"))
    if {index for index, _ in ranges} != {row["range_index"] for row in plan["ranges"]}:
        raise ValueError("frozen 257(2) range inventory differs from probe plan")
    by_index = {row["range_index"]: row for row in plan["ranges"]}
    impossible = []
    for index, source_row in ranges:
        row = by_index[index]
        if row["source_ref"]["sha256"] != source_hash or row["judgment_key"] != source_row["key"]:
            raise ValueError("frozen judgment range binding differs")
        low, high = source_row["minimum"], source_row["maximum"]
        if low < 0 or high < low:
            raise ValueError("unexpected nonnegative physical range")
        if low <= 0:
            raise ValueError("no nonnegative value strictly below training minimum")
        targets = row["planning_targets"]
        if row["variable"] == "counterpart_center_station":
            targets["below"], targets["inside"], targets["above"] = 0, 8, 35
        else:
            targets["below"] = low / 2
            targets["above"] = high + max(0.1, (high - low) / 10)
        row["endpoint_limits"] = []
        if low == high:
            targets["inside"] = None
            row["endpoint_limits"].append(
                "strict interior is empty because frozen training minimum equals maximum")
            row["status"] = "two_feasible_targets_interior_mathematically_impossible"
            impossible.append(index)
        else:
            if row["variable"] != "counterpart_center_station":
                targets["inside"] = (low + high) / 2
            row["status"] = "three_targets_planned_unmeasured"
        if not 0 <= targets["below"] < low < targets["above"]:
            raise ValueError("below/above target ordering failed")
        if targets["inside"] is not None and not low < targets["inside"] < high:
            raise ValueError("interior target ordering failed")
    plan["feasibility_note"] = (
        "Physical targets use nonnegative source observables and exact frozen training bounds. "
        "The equal-endpoint speed ranges cannot have a strictly interior value; "
        "operator or source correction is required if all three bins are mandatory. "
        "No target is an accepted original measurement or legal cutoff.")
    PLAN.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n")
    return {"range_count": len(ranges), "three_target_ranges": len(ranges) - len(impossible),
            "empty_interior_range_indices": impossible, "source_sha256": source_hash}


if __name__ == "__main__":
    print(json.dumps(refine(), sort_keys=True))
