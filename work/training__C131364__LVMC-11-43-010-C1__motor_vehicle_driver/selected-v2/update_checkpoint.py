"""Refresh truthful selected CPU checkpoint metadata from durable files."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def digest(relative):
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


path = ROOT / "result.json"
result = json.loads(path.read_text())
assert result["status"] == "partial"
result["reason"] = (
    "Two exact left-turn witnesses now have current-v2 600-frame/four-camera primary and "
    "matched fallback constructions. All four selected attempts pass offline, 11-check public "
    "compatibility and missing-source rejection, and recorded-only process-saved. Canonical "
    "semantic stages, canonical execution/package compatibility, source isolation, exact "
    "delivery contract, and CPU positive/negative "
    "physical-delivery and original-comparison audit logic pass. Native runner/finalizer have "
    "bounded fake-CARLA tests, but neither original CARLA attempt nor original pixels/physical "
    "roundabout review exists. Physical and legal outcomes, original comparison completion, "
    "case-plan camera/source observation mapping, and strict ready acceptance remain unverified."
)
result["source_law_review"] = (
    "Exact LVMC 11.43.010(C)(1) left-turn and U-turn alternatives reviewed. "
    "This fixed left-turn cell binds the left-turn pair; the separate exact-law C131055 "
    "assignment needs the U-turn binding and independent branch review."
)
cpu = result["current_v2_cpu"]
for key, rel in {
    "selected_manifest": "selected-v2-manifest.json",
    "selected_audit": "selected-v2/audit.json",
    "semantic_index": "proposals/semantic-index.json",
    "semantic_validation": "selected-v2/semantic-validation.json",
    "delivery_contract_validation": "selected-v2/delivery-contract-validation.json",
    "canonical_manifest": "execution-manifest.json",
    "canonical_validation": "selected-v2/canonical-validation.json",
    "root_unittest": "selected-v2/root-unittest.log",
    "physical_fixture_witness1": "selected-v2/physical/witness1/proof.json",
    "physical_fixture_witness2": "selected-v2/physical/witness2/proof.json",
    "delivery_audit_script": "selected-v2/delivery_audit.py",
    "comparison_audit_script": "selected-v2/comparison_audit.py",
    "comparison_positive_cpu_test": "selected-v2/comparison-positive.log",
    "comparison_negative_cpu_test": "selected-v2/comparison-negative.log",
    "statutory_branch_review": "proposals/statutory-branch-review.json",
}.items():
    cpu[key] = rel
    cpu[key + "_sha256"] = digest(rel)
cpu["selected_case_count"] = 2
cpu["selected_primary_and_fallback_proof_count"] = 4
cpu["selected_exact_public_compatibility_pass_count"] = 4
cpu["selected_recorded_only_processing_pass_count"] = 4
cpu["original_native_attempt_count"] = 0
cpu["physical_acceptance_claimed"] = False
cpu["legal_verdict_claimed"] = False
result["tests"] = [{"command": "PYTHONDONTWRITEBYTECODE=1 TMPDIR=$REPO/.runtime-work/c131364-selected/tmp PYTHONPATH=$REPO/work/" + ROOT.name + " $REPO/.venv-cpu/bin/python -m unittest discover -s tests -p test*.py (cwd work/" + ROOT.name + ")",
                    "exit_code": 0, "log": "selected-v2/root-unittest.log",
                    "sha256": digest("selected-v2/root-unittest.log")}]
path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
