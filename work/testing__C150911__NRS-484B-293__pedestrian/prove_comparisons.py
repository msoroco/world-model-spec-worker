"""Audit four declared crosswalk comparisons over saved diagnostic sources."""

import hashlib
import json
from pathlib import Path
import shutil

from crosswalk_delivery import audit_pair, measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def selected(case_id, source_root=None):
    short = case_id.split("__")[-1]
    attempt = source_root or REPO / ".runtime-work/c150911-compat-selected" / short / "primary"
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
        negative_root = REPO / ".runtime-work/c150911-comparison-negative" / row["comparison_id"]
        if negative_root.exists():
            shutil.rmtree(negative_root)
        negative_root.mkdir(parents=True)
        original = REPO / ".runtime-work/c150911-compat-selected" / row["case_ids"][1].split("__")[-1] / "primary"
        for name in ("original-pedestrian.jsonl", "original-obstacles.jsonl",
                     "original-participants.jsonl"):
            shutil.copy2(original / name, negative_root / name)
        try:
            selected(row["case_ids"][1], negative_root)
        except FileNotFoundError as error:
            if "original-site.json" not in str(error):
                raise
            source_rejection = "Missing required original-site.json rejected"
        else:
            raise ValueError("comparison accepted missing original site")
        altered = dict(right, fixed_sources=dict(right["fixed_sources"]))
        altered["fixed_sources"]["crosswalk_source_sha256"] = "changed-source"
        try:
            audit_pair(left, altered, allowed)
        except ValueError as error:
            if "fixed site differs" not in str(error):
                raise
            fixed_rejection = str(error)
        else:
            raise ValueError("comparison accepted changed fixed crosswalk")
        log = ROOT / ("comparison-negative-" + row["comparison_id"] + ".log")
        log.write_text(source_rejection + "\n" + fixed_rejection + "\n")
        audit["negative_log"] = str(log.relative_to(ROOT))
        audit["negative_log_sha256"] = hashlib.sha256(log.read_bytes()).hexdigest()
        audit["negative_source_rejection"] = source_rejection
        audit["negative_fixed_condition_rejection"] = fixed_rejection
        results.append(audit)
        print(row["comparison_id"], "passed")
    (ROOT / "cpu-comparison-proofs.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
