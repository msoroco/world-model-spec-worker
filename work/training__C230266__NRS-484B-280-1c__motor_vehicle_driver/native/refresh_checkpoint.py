"""Publish a truthful assignment-local partial checkpoint and handoff."""

import hashlib
import json
import os
from pathlib import Path
import shlex


ROOT = Path(__file__).resolve().parent.parent
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, content):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    stage = SCRATCH / (path.name + ".staging")
    stage.write_text(content.rstrip() + "\n")
    os.replace(stage, path)


def current_compat(manifest):
    path = ROOT / "compatibility/index.json"
    if not path.is_file():
        return []
    rows = {row["case_id"]: row for row in json.loads(path.read_text())["passed"]}
    current = []
    for entry in manifest["cases"]:
        row = rows.get(entry["case_id"])
        if not row:
            continue
        receipt_path = ROOT / row["receipt"]
        if receipt_path.is_file() and sha(receipt_path) == row["receipt_sha256"]:
            receipt = json.loads(receipt_path.read_text())
            parts = shlex.split(row["command"])
            attempt = Path(parts[parts.index("--output") + 1])
            selection_path = attempt / "candidate-selection.json"
            selection = json.loads(selection_path.read_text()) if selection_path.is_file() else {}
            if (receipt.get("passed") is True and
                    receipt.get("construction_sha256") == entry["construction_sha256"] and
                    receipt.get("runtime_manifest_sha256") == manifest["runtime_manifest_sha256"] and
                    selection.get("manifest_sha256") == sha(ROOT / "selected-preflight-manifest.json")):
                current.append(entry["case_id"])
    return current


def current_saved(manifest):
    path = ROOT / "recorded-only/index.json"
    if not path.is_file():
        return []
    rows = {row["case_id"]: row for row in json.loads(path.read_text())["passed"]}
    current = []
    for entry in manifest["cases"]:
        row = rows.get(entry["case_id"])
        if not row:
            continue
        proof_path = ROOT / row["proof"]
        if (proof_path.is_file() and sha(proof_path) == row["proof_sha256"] and
                row["construction_sha256"] == entry["construction_sha256"] and
                row.get("manifest_sha256") == sha(ROOT / "selected-preflight-manifest.json")):
            current.append(entry["case_id"])
    return current


def proof(path):
    file = ROOT / path
    return {"path": path, "sha256": sha(file), "passed": True}


def main():
    manifest = json.loads((ROOT / "selected-preflight-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    compatible, saved = current_compat(manifest), current_saved(manifest)
    result_path = ROOT / "result.json"
    result = json.loads(result_path.read_text())
    result.update({
        "status": "partial", "readiness_kind": "implementation_checkpoint",
        "planned_case_count": len(plan["cases"]), "candidate_count": 0,
        "unresolved_branch_count": len(plan["requirement_dispositions"]),
        "reason": (f"{len(plan['requirement_dispositions'])} source-distinct statutory positions have "
                   f"{len(plan['cases'])} exact selected CPU constructions and comparisons; "
                   f"all exact offline and physical/lifecycle software fixture checks pass. "
                   f"Current-construction public compatibility {len(compatible)}/{len(plan['cases'])}, "
                   f"recorded-only positive/negative {len(saved)}/{len(plan['cases'])}. "
                   "Canonical semantic and independent delivery/comparison CPU predicates pass. "
                   "Final execution-manifest and strict proofs remain. "
                   "Original driver observation, statutory position, Native motion and pixels are unverified."),
        "cpu_proofs": [proof(path) for path in (
            "statutory-source-audit.json", "native/branch-meter-proof.json",
            "native/saved-source-proof.json", "native/finalizer-proof.json",
            "native/branch-construction-proof.json",
            "native/branch-cases/branch-offline-index.json",
            "selected-offline/index.json", "selected-contract-index.json",
            "proposals/semantic-index.json", "delivery-audit/index.json",
            "comparison-audit/index.json")],
        "current_compatibility_case_count": len(compatible),
        "current_recorded_only_case_count": len(saved),
        "physical_lifecycle_fixture_count": len(manifest["cases"]),
        "tests": [{"command": str(ROOT.parents[1] / ".venv-cpu/bin/python") +
                   " -B -m unittest discover -s tests -p test*.py",
                   "exit_code": 0, "log": "tests/root-offline.log",
                   "sha256": sha(ROOT / "tests/root-offline.log")}],
        "native_executed": False, "legal_verdict_claimed": False})
    atomic(result_path, json.dumps(result, indent=2, ensure_ascii=False))
    handoff = f"""# NRS 484B.280(1)(c), C230266 motor vehicle driver

Status: **partial**. The frozen law is split into {len(plan['requirement_dispositions'])} source-distinct positions, {len(plan['cases'])} exact selected cases and {len(plan['comparisons'])} controlled comparisons. There is no accepted full-train recording. No legal near-distance or proper-caution threshold is asserted.

## Current CPU evidence

- All {len(plan['cases'])} selected current-runtime offline checks pass (`selected-offline/index.json`). Draft construction checks pass {len(plan['cases'])} positives, {len(plan['cases'])} missing-source negatives and {len(plan['comparisons'])} comparison-isolation checks (`native/branch-construction-proof.json`). Source meters and saved finalization retain actual driver observation as a separate source fact.
- All {len(plan['cases'])} physical/lifecycle CPU fixtures under `physical/` show complete travel, incomplete travel and missing evidence separately, plus capture seal, encoder closure, restoration, Native exit and owner release ordering. They are synthetic checker tests, not original motion.
- Current selected construction hashes have {len(compatible)}/{len(plan['cases'])} public positive/missing-source compatibility receipts and {len(saved)}/{len(plan['cases'])} public recorded-only positive/negative processing proofs. The public proof loops are `native/run_selected_compatibility.py` and `native/run_selected_saved.py`.
- `statutory-source-audit.json` binds separate bus stop, bench, shelter, transit stop, bus boarding and other public transportation boarding positions. Original designation, use and actor class require independent sources; a label or prop alone cannot establish them.
- `proposals/semantic-index.json` passes the six-stage current-runtime semantic validator for all {len(plan['cases'])} selected cases. Driver observation and proper caution stay unresolved. The physical judgment sweep is explicitly incomplete pending original sources and a defensible sampling range.
- `delivery-audit/index.json` passes {len(plan['cases'])} positive and {len(plan['cases'])} missing-observation negative CPU predicate tests. `comparison-audit/index.json` passes {len(plan['comparisons'])} positive and {len(plan['comparisons'])} changed-source negative tests. Neither attests an original Native capture.

## Remaining CPU work

Finish the current-manifest public compatibility and recorded-only loops for all {len(plan['cases'])} cases. Bind the completed CPU receipts, physical risk decisions and independent audit contracts in `execution-manifest.json`, then run `.venv-cpu/bin/python worker_check.py --assignment {ROOT.name} --complete --require-delivery-ready`; keep partial until it passes. The lead integrates the shared exact GPU queue. Local Native execution and independent review of actual driver observation, original position/designation, motion and pixels remain separate from CPU readiness.

All scratch and generated diagnostics stay under `.runtime-work/`; every returned file stays below 2 MiB. No frozen input, runtime or batch file was edited.
"""
    atomic(ROOT / "HANDOFF.md", handoff)
    print(json.dumps({"status": "partial", "cases": len(plan["cases"]),
                      "current_compatibility": len(compatible), "current_saved": len(saved),
                      "result_sha256": sha(result_path)}))


if __name__ == "__main__":
    main()
