"""Independent validation of twenty exact CPU audit receipts and rejection gates."""
import copy
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline"))
from scenario_pipeline.worker_exchange.delivery_handoff import validate_case


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(entry):
    try:
        validate_case(HERE, entry, ["full-train"])
    except ValueError:
        return
    raise AssertionError("Corrupt delivery acceptance proof accepted")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if len(manifest["cases"]) != 20:
        raise AssertionError("Twenty selected cases required")
    results = []
    for entry in manifest["cases"]:
        contract = validate_case(HERE, entry, ["full-train"])
        positive = json.loads((HERE / contract["test_log"]).read_text())
        if (positive["case_id"] != entry["case_id"] or
                positive["construction_sha256"] != entry["construction_sha256"] or
                positive["auditor_sha256"] != contract["script_sha256"] or
                positive["source_shape_passed"] is not True or
                positive["delivery_accepted"] is not False or
                positive["actual_pixels_reviewed"] is not False or
                positive["original_native_motion_verified"] is not False):
            raise AssertionError("Diagnostic acceptance proof differs")
        for corruption in ("script_sha256", "test_log_sha256", "negative_log_sha256"):
            altered = copy.deepcopy(entry)
            altered["delivery_acceptance"][corruption] = "0" * 64
            rejected(altered)
        results.append({"case_id": entry["case_id"], "positive_sha256": contract["test_log_sha256"],
                        "negative_sha256": contract["negative_log_sha256"]})
    proof = {"format": "c110919-selected-delivery-acceptance-cpu-proof-v1",
             "manifest_sha256": sha(manifest_path), "case_count": len(results),
             "validator_corruptions_rejected": len(results) * 3,
             "accepted_recordings": 0, "original_pixels_reviewed": False,
             "cases": results}
    path = HERE / "update061-selected-delivery-acceptance-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(results),
                      "validator_corruptions_rejected": proof["validator_corruptions_rejected"],
                      "proof_sha256": sha(path), "accepted_recordings": 0}))


if __name__ == "__main__":
    main()
