"""Audit four declared crosswalk comparisons over saved diagnostic sources."""

import hashlib
import json
from pathlib import Path

from crosswalk_delivery import audit_pair, measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def selected(case_id):
    short = case_id.split("__")[-1]
    attempt = REPO / ".runtime-work/c150911-compat-selected" / short / "primary"
    site = json.loads((attempt / "original-site.json").read_text())
    streams = [[json.loads(s) for s in (attempt / name).read_text().splitlines()]
               for name in ("original-pedestrian.jsonl", "original-obstacles.jsonl",
                            "original-participants.jsonl")]
    motion = measure(site, *streams)
    motion["original_trace_sha256"] = hashlib.sha256(
        (attempt / "original-pedestrian.jsonl").read_bytes()).hexdigest()
    return motion


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    results = []
    for row in plan["comparisons"]:
        left, right = [selected(cid) for cid in row["case_ids"]]
        differences = set(row["deliberate_differences"])
        allowed = {"obstacle_source_sha256"} if "obstacle_context" in differences else set()
        audit = audit_pair(left, right, allowed)
        if left["original_trace_sha256"] == right["original_trace_sha256"]:
            raise ValueError("comparison reuses identical original walker trace")
        lateral = [sum(point["right_lateral_m"] for point in motion["full_original_trace"])
                   for motion in (left, right)]
        if row["comparison_id"] in ("forward_half", "reverse_half") and not (
                lateral[0] > 0 and lateral[1] < 0):
            raise ValueError("direction-relative half comparison not realized")
        if row["comparison_id"] == "directional_right" and not all(v > 0 for v in lateral):
            raise ValueError("opposite directions did not retain relative right half")
        if row["comparison_id"] == "right_half_obstruction" and (
                left["fixed_sources"]["obstacle_source_sha256"] ==
                right["fixed_sources"]["obstacle_source_sha256"]):
            raise ValueError("declared obstruction source did not change")
        audit.update({"comparison_id": row["comparison_id"], "case_ids": row["case_ids"],
            "declared_differences": row["deliberate_differences"],
            "original_trace_sha256": [left["original_trace_sha256"],
                                      right["original_trace_sha256"]],
            "direction_relative_lateral_sums_m": lateral,
            "diagnostic_only": True, "physical_acceptance": False,
            "legal_practicability": "unresolved"})
        results.append(audit)
        print(row["comparison_id"], "passed")
    (ROOT / "cpu-comparison-proofs.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
