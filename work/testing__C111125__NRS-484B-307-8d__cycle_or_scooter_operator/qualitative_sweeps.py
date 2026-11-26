"""Source-gated categorical contrasts for the two unresolved judgment phrases.

These contrasts reuse selected exact cases. They establish measured differences
only after independent original-source, pixel and delivery audits. They do not
replace the two source-pending numeric sweep specifications or decide the law.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_delivery import audit as audit_comparison

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
AXES = {
    "detector_causality": ("failed_detection_vs_signal_change",
                           "two_cycles_failed_detection", "signal_changes",
                           "detector failure observed versus signal change"),
    "directed_yield": ("yield_to_directed_participant",
                       "two_cycles_failed_detection", "fails_to_yield",
                       "yield before directed participant versus conflict at entry"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    case_plan = json.loads((HERE / "case-plan.json").read_text())
    selected = {row["case_id"]: row for row in manifest["cases"]}
    comparisons = {row["comparison_id"]: row for row in case_plan["comparisons"]}
    axes = []
    for name, (comparison_id, left, right, difference) in AXES.items():
        ids = [ASSIGNMENT + "__" + left, ASSIGNMENT + "__" + right]
        if comparison_id not in comparisons or comparisons[comparison_id]["case_ids"] != ids:
            raise ValueError("selected qualitative comparison identity differs: " + name)
        if not all(case in selected for case in ids):
            raise ValueError("selected qualitative case missing: " + name)
        axes.append({"axis_id": name, "comparison_id": comparison_id,
                     "case_ids": ids, "construction_sha256":
                     [selected[case]["construction_sha256"] for case in ids],
                     "fixed_conditions": comparisons[comparison_id]["fixed_conditions"],
                     "deliberate_difference": difference,
                     "review_gate": "comparison_delivery.audit in original mode with both site and pixel reviews",
                     "legal_conclusion": None, "realized_original_difference_claimed": False})
    return {"format": "c111125-source-gated-qualitative-sweeps-v1",
            "assignment_id": ASSIGNMENT,
            "assignment_source_sha256": sha(REPO / "inputs" / ASSIGNMENT / "assignment.json"),
            "manifest_sha256": sha(manifest_path),
            "case_plan_sha256": sha(HERE / "case-plan.json"),
            "comparison_auditor_sha256": sha(HERE / "comparison_delivery.py"),
            "axes": axes, "diagnostic_fixture": False,
            "physical_acceptance": False, "legal_conclusion": None}


def review(plan: dict, paths: dict[str, dict[str, Path]]) -> dict:
    current = build()
    if plan != current or set(paths) != set(AXES):
        raise ValueError("qualitative sweep plan stale or incomplete")
    receipts = []
    for axis in current["axes"]:
        values = paths[axis["axis_id"]]
        if set(values) != {"left_attempt", "right_attempt", "left_processed",
                           "right_processed", "authority_root", "left_site",
                           "right_site", "left_review", "right_review"}:
            raise ValueError("both original attempts, sites, and pixel reviews required")
        receipt = audit_comparison(axis["comparison_id"], values["left_attempt"],
                                   values["right_attempt"], values["left_processed"],
                                   values["right_processed"], values["authority_root"],
                                   values["left_site"], values["right_site"],
                                   values["left_review"], values["right_review"],
                                   diagnostic=False)
        if (receipt.get("comparison_id") != axis["comparison_id"] or
                receipt.get("case_ids") != axis["case_ids"] or
                receipt.get("diagnostic_fixture") is not False or
                receipt.get("physical_acceptance") is not False or
                receipt.get("legal_verdict") is not None):
            raise ValueError("original qualitative comparison receipt differs")
        receipts.append(receipt)
    return {"format": "c111125-original-qualitative-sweep-review-v1",
            "assignment_id": ASSIGNMENT, "plan_sha256": hashlib.sha256(
                (json.dumps(plan, sort_keys=True) + "\n").encode()).hexdigest(),
            "comparisons": receipts, "physical_acceptance": False,
            "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--input", type=Path, help="JSON with both original nine-path comparisons")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior sweep output")
    if args.plan is None:
        if args.input is not None:
            raise ValueError("review needs frozen qualitative plan")
        result = build()
    else:
        if args.input is None:
            raise ValueError("review needs original comparison paths")
        plan = json.loads(args.plan.read_text())
        values = json.loads(args.input.read_text())
        result = review(plan, {key: {name: Path(value) for name, value in paths.items()}
                               for key, paths in values.items()})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"axes": len(result.get("axes", result.get("comparisons", []))),
                      "original_reviewed": args.plan is not None}))


if __name__ == "__main__":
    main()
