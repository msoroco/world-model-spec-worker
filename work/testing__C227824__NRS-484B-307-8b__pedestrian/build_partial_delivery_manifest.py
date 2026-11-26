"""Select the six exact CPU bundles while preserving the original-source gap.

This manifest is a partial handoff. Synthetic diagnostic receipts never become
production delivery or physical acceptance receipts here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    return json.loads(path.read_text())


def build() -> dict:
    plan = _read(HERE / "case-plan.json")
    proposal = _read(HERE / "proposals/cases.json")
    draft = _read(HERE / "execution-manifest.draft.json")
    index = _read(HERE / "draft-proof-index.json")
    aid = HERE.name
    expected = {case["case_id"] for case in plan["cases"]}
    semantic = {case["case_id"] for case in proposal["cases"]
                if case.get("target_type") != "baseline"}
    if (draft.get("assignment_id") != aid or index.get("assignment_id") != aid
            or expected != semantic or expected != {case["case_id"] for case in draft["cases"]}
            or len(expected) != 9):
        raise ValueError("nine exact selected cases differ")
    if index["execution_manifest_sha256"] != _sha(HERE / "execution-manifest.draft.json"):
        raise ValueError("draft proof index changed")
    if index["semantic_index_sha256"] != _sha(HERE / "proposals/semantic-index.json"):
        raise ValueError("semantic proof binding changed")
    proof_by_case = {case["case_id"]: case for case in index["cases"]}
    if set(proof_by_case) != expected:
        raise ValueError("diagnostic proof case coverage differs")
    entries = []
    for case in draft["cases"]:
        cid = case["case_id"]
        suffix = cid.rsplit("__", 1)[1]
        proof = proof_by_case[cid]
        source = HERE / case["construction"]
        if _sha(source) != case["construction_sha256"] or proof["construction_sha256"] != case["construction_sha256"]:
            raise ValueError("selected construction hash differs: " + cid)
        paths = {"measurement_contract_sha256": HERE / case["measurement_contract"],
                 "fixture_recipe_sha256": HERE.parents[1] / case["fixture_recipe"],
                 "compatibility_receipt_sha256": HERE / case["compatibility"]["receipt"],
                 "saved_positive_diagnostic_sha256": HERE / "cases" / suffix / "saved-positive-diagnostic.json",
                 "saved_negative_diagnostic_sha256": HERE / "cases" / suffix / "saved-negative-diagnostic.json",
                 "physical_preparation_sha256": HERE / "physical-preparation" / (suffix + "-proof.json")}
        for key, path in paths.items():
            if _sha(path) != proof[key]:
                raise ValueError("selected diagnostic proof hash differs: " + cid + " " + key)
        entry = dict(case)
        entry["proof_status"] = "diagnostic_cpu_only_source_review_pending"
        entry["physical_preparation"] = {
            "receipt": "physical-preparation/" + suffix + "-proof.json",
            "sha256": proof["physical_preparation_sha256"]}
        entry["saved_processing_diagnostic"] = {
            "positive": "cases/" + suffix + "/saved-positive-diagnostic.json",
            "positive_sha256": proof["saved_positive_diagnostic_sha256"],
            "negative": "cases/" + suffix + "/saved-negative-diagnostic.json",
            "negative_sha256": proof["saved_negative_diagnostic_sha256"]}
        entry["production_source_audit"] = {
            "script": "delivery_audit.py", "script_sha256": _sha(HERE / "delivery_audit.py"),
            "command": ".venv-cpu/bin/python work/" + aid + "/delivery_audit.py"
                       " --attempt $ORIGINAL_ATTEMPT --case " + cid +
                       " --output $DELIVERY_AUDIT_RECEIPT",
            "status": "pending_original_native_attempt"}
        entry["missing_proofs"] = [
            "reviewed official route-facing signal/controller and pedestrian device driver",
            "reviewed full highway boundary and camera placement sources",
            "expanded source-backed NRS 484B.283 permission sweep",
            "original Native acquisition and independent delivery audit"]
        entries.append(entry)
    comparison_proofs = {item["comparison_id"]: item["sha256"] for item in index["comparisons"]}
    if set(comparison_proofs) != {item["comparison_id"] for item in plan["comparisons"]}:
        raise ValueError("selected comparison coverage differs")
    comparisons = []
    for item in plan["comparisons"]:
        ident = item["comparison_id"]
        path = HERE / "comparisons" / (ident + "-diagnostic.json")
        if _sha(path) != comparison_proofs[ident]:
            raise ValueError("selected comparison diagnostic changed: " + ident)
        comparisons.append({"comparison_id": ident,
                            "diagnostic_receipt": str(path.relative_to(HERE)),
                            "diagnostic_sha256": comparison_proofs[ident],
                            "production_script": "comparison_delivery.py",
                            "production_script_sha256": _sha(HERE / "comparison_delivery.py"),
                            "production_command": ".venv-cpu/bin/python work/" + aid +
                                "/comparison_delivery.py --left-attempt $LEFT_ORIGINAL_ATTEMPT"
                                " --right-attempt $RIGHT_ORIGINAL_ATTEMPT"
                                " --comparison-id " + ident +
                                " --output $COMPARISON_AUDIT_RECEIPT",
                            "status": "pending_original_native_pair"})
    manifest = {"format": "worker-execution-manifest", "assignment_id": aid,
                "runtime_manifest_sha256": draft["runtime_manifest_sha256"],
                "semantic_index_sha256": index["semantic_index_sha256"],
                "status": "partial", "cases": entries, "comparisons": comparisons,
                "source_gate": {"sweep_id": "c227824-other-device-permission",
                                "status": "incomplete", "physical_acceptance_claimed": False,
                                "legal_verdict_claimed": False}}
    (HERE / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    selected = build()
    print(json.dumps({"cases": len(selected["cases"]),
                      "comparisons": len(selected["comparisons"]),
                      "status": selected["status"]}))
