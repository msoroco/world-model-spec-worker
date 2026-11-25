"""Bind all current CPU proofs without selecting an unsourced production case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def build() -> dict:
    index = load(HERE / "diagnostic-compatibility-index-all.json")
    manifest = load(HERE / "execution-manifest.diagnostic.json")
    matrix = load(HERE / "statutory-matrix.draft.json")
    plan = load(HERE / "case-plan.json")
    proposal = load(HERE / "proposals/cases.json")
    aid = HERE.name
    expected = set(matrix["accepted_recordings"])
    if (index.get("assignment_id") != aid or manifest.get("assignment_id") != aid
            or index.get("manifest_sha256") != sha(HERE / "execution-manifest.diagnostic.json")
            or index.get("diagnostic_only") is not True
            or index.get("source_kind") != "synthetic_fixture"
            or {row["case_id"] for row in plan["cases"]} != expected
            or {row["case_id"] for row in proposal["cases"] if row["target_type"] != "baseline"} != expected
            or {row["case_id"] for row in manifest["cases"]} != expected
            or len(expected) != 11):
        raise ValueError("diagnostic, statutory and semantic exact cases differ")
    if proposal.get("sweeps_expanded") is not False:
        raise ValueError("source-gated sweep status changed; use production selection")
    proof_by_case = {row["case_id"]: row for row in index["case_proofs"]}
    entry_by_case = {row["case_id"]: row for row in manifest["cases"]}
    if set(proof_by_case) != expected:
        raise ValueError("diagnostic proof case coverage differs")
    cases = []
    for cid in sorted(expected):
        proof, entry = proof_by_case[cid], entry_by_case[cid]
        kind = cid.rsplit("__", 1)[1]
        if (entry["kind"] != "capability_research"
                or proof["construction_sha256"] != entry["construction_sha256"]
                or sha(HERE / entry["construction"]) != entry["construction_sha256"]
                or sha(ROOT / entry["fixture_recipe"]) != proof["fixture_recipe_sha256"]
                or sha(HERE / entry["measurement_contract"]) != proof["measurement_contract_sha256"]):
            raise ValueError("diagnostic exact case construction changed: " + cid)
        for phase in ("offline", "compatibility", "saved"):
            item = proof["logs"][phase]
            if sha(HERE / item["path"]) != item["sha256"]:
                raise ValueError("diagnostic phase log changed: " + cid + " " + phase)
        if proof["compatibility_receipt"]["passed"] is not True or proof["physical_acceptance_claimed"] is not False:
            raise ValueError("diagnostic proof status differs: " + cid)
        cases.append({"case_id": cid, "source_kind": "synthetic_fixture",
                      "diagnostic_construction": entry["construction"],
                      "diagnostic_construction_sha256": entry["construction_sha256"],
                      "cpu_proof_logs": proof["logs"],
                      "production_builder_command": ".venv-cpu/bin/python work/" + aid +
                          "/build_production_construction.py --kind " + kind +
                          " --site $REVIEWED_SITE --output $PRODUCTION_CONSTRUCTION",
                      "original_source_audit_command": ".venv-cpu/bin/python work/" + aid +
                          "/selected_delivery_audit.py --stage $SAVED_STAGE --case " + cid +
                          " --output $SOURCE_AUDIT_RECEIPT",
                      "status": "original_source_pending"})
    comparison = HERE / "diagnostic-comparison-all.json"
    checks = load(comparison)
    planned = {row["comparison_id"] for row in plan["comparisons"]}
    if (sha(comparison) != index["comparison_sha256"]
            or checks.get("diagnostic_fixture") is not True
            or {row["comparison_id"] for row in checks["comparisons"]} != planned
            or len(planned) != 8):
        raise ValueError("eight diagnostic comparisons differ")
    result = {"format": "c158208-selected-cpu-handoff-v1", "assignment_id": aid,
              "status": "partial_original_source_pending", "diagnostic_only": True,
              "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
              "diagnostic_manifest_sha256": sha(HERE / "execution-manifest.diagnostic.json"),
              "diagnostic_index_sha256": sha(HERE / "diagnostic-compatibility-index-all.json"),
              "semantic_index_sha256": sha(HERE / "proposals/semantic-index.json"),
              "statutory_matrix_sha256": sha(HERE / "statutory-matrix.draft.json"),
              "cases": cases,
              "comparisons": [{"comparison_id": cid} for cid in sorted(planned)],
              "production_auditors": {name: sha(HERE / name) for name in
                                      ("selected_delivery_audit.py", "statutory_comparison_audit.py",
                                       "source_grounded_sweeps.py", "build_source_gated_manifest.py")},
              "production_comparison_command": ".venv-cpu/bin/python work/" + aid +
                  "/statutory_comparison_audit.py --stages $ORIGINAL_SAVED_STAGES"
                  " --reviewed-expectations $REVIEWED_EXPECTATIONS"
                  " --output $COMPARISON_AUDIT_RECEIPT",
              "source_gate": {"reviewed_site": "absent", "original_map": "absent",
                              "adjacent_surveys": 8, "judgment_sweeps": 4,
                              "canonical_production_manifest": "not_selected"}}
    output = HERE / "selected-cpu-handoff.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    return {"cases": len(cases), "comparisons": len(planned), "sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
