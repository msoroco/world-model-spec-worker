"""Bind every controlled comparison to the selected cases and original auditor."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    receipt = json.loads((HERE / "comparison-audit-receipt.json").read_text())
    selected = {case["case_id"] for case in manifest["cases"]}
    diagnostics = {item["comparison_id"]: item for item in receipt["comparisons"]}
    if len(selected) != 8 or len(diagnostics) != len(plan["comparisons"]) != 7:
        raise ValueError("selected comparison coverage incomplete")
    auditor = HERE / "audit_original_comparisons.py"
    if not auditor.is_file():
        raise ValueError("original comparison auditor missing")
    entries = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        cases = comparison["case_ids"]
        if len(cases) != 2 or not set(cases) <= selected:
            raise ValueError("comparison references unselected case: " + ident)
        diagnostic = diagnostics.get(ident)
        if diagnostic is None or diagnostic["case_ids"] != cases or not diagnostic.get("diagnostic_fixture"):
            raise ValueError("diagnostic comparison missing or mismatched: " + ident)
        command = (
            f".venv-cpu/bin/python work/{AID}/audit_original_comparisons.py"
            f" --comparison {ident} --left-attempt $LEFT_ORIGINAL_ATTEMPT"
            f" --right-attempt $RIGHT_ORIGINAL_ATTEMPT"
            f" --reviewed-site-sha256 $REVIEWED_SITE_SHA256"
            f" --reviewed-vehicle-sha256 $REVIEWED_VEHICLE_SHA256"
            f" --output $COMPARISON_AUDIT_OUTPUT"
        )
        entries.append({"comparison_id": ident, "case_ids": cases,
                        "fixed_conditions": comparison["fixed_conditions"],
                        "deliberate_differences": comparison["deliberate_differences"],
                        "diagnostic_only": True,
                        "original_audit_command": command})
    index = {"format": "c135087-selected-comparison-index-v1",
             "assignment_id": AID,
             "selected_manifest_sha256": sha(HERE / "execution-manifest.json"),
             "case_plan_sha256": sha(HERE / "case-plan.json"),
             "diagnostic_receipt_sha256": sha(HERE / "comparison-audit-receipt.json"),
             "original_auditor_sha256": sha(auditor),
             "comparisons": entries,
             "original_comparisons_accepted": False}
    (HERE / "selected-comparison-audits.json").write_text(
        json.dumps(index, indent=2) + "\n")
    print("bound seven selected comparisons to original source-gated audit")


if __name__ == "__main__":
    main()
