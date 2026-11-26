"""Bind current nine-case CPU diagnostics without claiming Native delivery."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SAVED = REPO / ".runtime-work/c227824-saved-processing-v1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    plan = read(ROOT / "case-plan.json")
    draft = read(ROOT / "execution-manifest.draft.json")
    entries = {case["case_id"]: case for case in draft["cases"]}
    if len(entries) != 9 or set(entries) != {case["case_id"] for case in plan["cases"]}:
        raise ValueError("nine exact draft cases required")
    case_proofs = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        entry = entries[case_id]
        target = ROOT / "cases" / suffix
        positive = SAVED / suffix / "positive-versions/v0001/processing.json"
        negative = SAVED / suffix / "negative-versions/v0001/feedback.json"
        pos, neg = read(positive), read(negative)
        if (pos.get("case_id") != case_id or pos.get("passed") is not True or
                pos.get("recorded_only") is not True or
                neg.get("missing_evidence") is not True and
                "Missing required source: device-history.jsonl" not in neg.get("error", "")):
            raise ValueError("saved diagnostic positive/negative mismatch: " + case_id)
        positive_receipt = {"format": "worker-saved-diagnostic-binding",
                            "case_id": case_id, "recorded_only": True,
                            "diagnostic_fixture": True,
                            "processing_sha256": sha(positive),
                            "construction_sha256": entry["construction_sha256"],
                            "physical_acceptance_claimed": False}
        negative_receipt = {"format": "worker-saved-diagnostic-rejection",
                            "case_id": case_id, "recorded_only": True,
                            "diagnostic_fixture": True,
                            "feedback_sha256": sha(negative),
                            "missing_device_source_rejected": True,
                            "physical_acceptance_claimed": False}
        write(target / "saved-positive-diagnostic.json", positive_receipt)
        write(target / "saved-negative-diagnostic.json", negative_receipt)
        paths = {"measurement_contract_sha256": ROOT / entry["measurement_contract"],
                 "fixture_recipe_sha256": REPO / entry["fixture_recipe"],
                 "compatibility_receipt_sha256": ROOT / entry["compatibility"]["receipt"],
                 "saved_positive_diagnostic_sha256": target / "saved-positive-diagnostic.json",
                 "saved_negative_diagnostic_sha256": target / "saved-negative-diagnostic.json",
                 "physical_preparation_sha256": ROOT / "physical-preparation" / (suffix + "-proof.json")}
        case_proofs.append({"case_id": case_id,
                            "construction_sha256": entry["construction_sha256"],
                            **{key: sha(path) for key, path in paths.items()}})
    comparisons = []
    for item in plan["comparisons"]:
        path = ROOT / "comparisons" / (item["comparison_id"] + "-diagnostic.json")
        proof = read(path)
        if proof.get("comparison_id") != item["comparison_id"] or proof.get("diagnostic_audit_passed") is not True:
            raise ValueError("diagnostic comparison mismatch: " + item["comparison_id"])
        comparisons.append({"comparison_id": item["comparison_id"], "sha256": sha(path)})
    index = {"format": "c227824-draft-proof-binding", "assignment_id": ROOT.name,
             "status": "draft_partial", "physical_acceptance_claimed": False,
             "execution_manifest_sha256": sha(ROOT / "execution-manifest.draft.json"),
             "semantic_index_sha256": sha(ROOT / "proposals/semantic-index.json"),
             "case_count": len(case_proofs), "cases": case_proofs,
             "comparisons": comparisons,
             "saved_processing_summary_sha256": sha(ROOT / "cpu-saved-processing-current.log"),
             "production_delivery_negative_sha256": sha(ROOT / "cpu-delivery-negative-current.log")}
    write(ROOT / "draft-proof-index.json", index)
    print(json.dumps({"bound_cases": len(case_proofs), "bound_comparisons": len(comparisons),
                      "status": "diagnostic_cpu_only"}))


if __name__ == "__main__":
    main()
