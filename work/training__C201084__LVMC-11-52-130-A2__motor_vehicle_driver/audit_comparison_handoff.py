"""Bind all selected CPU comparison diagnostics to the final delivery plan."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = {
    "comparison_main": "final-reference-contrast-audit.json",
    "comparison_lead_position": "final-conflict-clear-audit.json",
    "comparison_lead_presence": "final-traffic-pair-audit.json",
}


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    plan = read(HERE / "case-plan.json")
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    chains_path = HERE / "final-chains-audit.json"
    chains = read(chains_path)
    queue_path = ROOT / "work/_shared/gpu-queue.json"
    queue = read(queue_path)
    manifest_sha = sha(manifest_path)
    chains_sha = sha(chains_path)
    selected = {entry["case_id"] for entry in manifest["cases"]}
    require(chains["passed"] is True and
            chains["final_manifest_sha256"] == manifest_sha and
            chains["candidate_chains_proven"] == 32,
            "Final candidate proofs are missing or stale")
    require(len(selected) == 8, "Expected eight exact selected cases")
    comparisons = plan["comparisons"]
    require(len(comparisons) == len(SOURCES) and
            {item["comparison_id"].rsplit("__", 1)[-1] for item in comparisons} == set(SOURCES),
            "Comparison plan differs from the three independent audits")
    queue_rows = {row["comparison_id"]: (index, row)
                  for index, row in enumerate(queue["comparison_audit_commands"])
                  if row["assignment_id"] == HERE.name}
    require(len(queue_rows) == 3, "Selected comparison queue coverage differs")
    bindings = []
    for item in comparisons:
        cid = item["comparison_id"]
        suffix = cid.rsplit("__", 1)[-1]
        path = HERE / SOURCES[suffix]
        proof = read(path)
        require(len(item["case_ids"]) == 2 and set(item["case_ids"]) <= selected,
                "Comparison references an unselected case: " + cid)
        require(proof["passed"] is True and proof["diagnostic_only"] is True and
                proof["accepted"] is False and
                proof["final_manifest_sha256"] == manifest_sha and
                proof["final_chains_audit_sha256"] == chains_sha,
                "Independent diagnostic is missing or stale: " + cid)
        embedded = proof.get("comparison", proof)
        require(embedded.get("comparison_id", cid) == cid and
                embedded.get("passed") is True,
                "Comparison identity or result differs: " + cid)
        queue_index, row = queue_rows[cid]
        require(row["selected"] is True and row["dispatchable"] is False and
                row["status"] == "partial" and
                set(item["case_ids"]) <= set(row.get("case_ids", item["case_ids"])),
                "Queue intent differs: " + cid)
        bindings.append({"comparison_id": cid, "case_ids": item["case_ids"],
                         "deliberate_differences": item["deliberate_differences"],
                         "fixed_conditions": item["fixed_conditions"],
                         "audit": str(path.relative_to(ROOT)), "audit_sha256": sha(path),
                         "queue_index": queue_index})
    return {"format": "c201084-comparison-handoff-cpu-v1", "passed": True,
            "assignment_id": HERE.name, "manifest_sha256": manifest_sha,
            "candidate_chain_audit_sha256": chains_sha,
            "queue_sha256": sha(queue_path), "comparisons": bindings,
            "diagnostic_only": True, "original_native_observed": False,
            "canonical_comparison_accepted": False}


if __name__ == "__main__":
    result = audit()
    (HERE / "comparison-handoff-cpu.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparisons": len(result["comparisons"])}, sort_keys=True))
