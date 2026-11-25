"""Bind all planned comparisons to selected cases and source-gated audits."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    proof_index = json.loads((ROOT / "independent/installed-bound-proof-index.json").read_text())
    selected = {item["case_id"] for item in manifest["cases"]}
    if len(selected) != 6 or len(plan["comparisons"]) != 4:
        raise ValueError("selected comparison coverage incomplete")
    proof_rows = proof_index["proofs"]
    entries = []
    for comparison in plan["comparisons"]:
        ident = comparison["comparison_id"]
        cases = comparison["case_ids"]
        if len(cases) != 2 or not set(cases) <= selected:
            raise ValueError("comparison references an unselected case: " + ident)
        matches = [row for row in proof_rows if
                   f"prove_comparison_audit.py {ident} " in row.get("command", "")]
        if len(matches) != 1 or matches[0]["exit_code"] != 0:
            raise ValueError("comparison protocol proof missing: " + ident)
        proof = matches[0]
        path = ROOT / proof["log"]
        if not path.is_file() or sha(path) != proof["sha256"]:
            raise ValueError("comparison proof log changed: " + ident)
        if ("measured diagnostic positive and missing-pixel/source negatives passed"
                not in path.read_text()):
            raise ValueError("comparison protocol negatives did not run: " + ident)
        command = (
            f".venv-cpu/bin/python work/{AID}/independent/comparison_audit.py"
            f" --comparison-id {ident} --baseline-attempt $BASELINE_ORIGINAL_ATTEMPT"
            f" --changed-attempt $CHANGED_ORIGINAL_ATTEMPT"
            f" --baseline-delivery $BASELINE_DELIVERY_RECEIPT"
            f" --changed-delivery $CHANGED_DELIVERY_RECEIPT"
            f" --output $COMPARISON_AUDIT_OUTPUT"
        )
        entries.append({"comparison_id": ident, "case_ids": cases,
                        "fixed_conditions": comparison["fixed_conditions"],
                        "deliberate_differences": comparison["deliberate_differences"],
                        "diagnostic_positive_and_inline_negatives": proof,
                        "original_audit_command": command,
                        "original_accepted": False})
    audit = ROOT / "independent/comparison_audit.py"
    index = {"format": "c150041-selected-comparison-index-v1",
             "assignment_id": AID,
             "selected_manifest_sha256": sha(ROOT / "execution-manifest.json"),
             "case_plan_sha256": sha(ROOT / "case-plan.json"),
             "proof_index_sha256": sha(ROOT / "independent/installed-bound-proof-index.json"),
             "original_auditor_sha256": sha(audit),
             "comparisons": entries}
    (ROOT / "selected-comparison-audits.json").write_text(json.dumps(index, indent=2) + "\n")
    print("bound four exact selected comparisons to positive/negative proofs and original audit")


if __name__ == "__main__":
    main()
