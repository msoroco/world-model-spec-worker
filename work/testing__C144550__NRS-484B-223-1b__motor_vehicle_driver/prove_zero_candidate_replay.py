"""Verify four zero-case candidate receipts against returned current-runtime sources."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + "__left_signal_at_departure_clear_gap"
FILES = HERE / "cases/left_signal_at_departure_clear_gap"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove():
    manifest_path = HERE / "zero-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entry = manifest["cases"][0]
    current_runtime = sha(ROOT / "runtime/SOURCE-MANIFEST.json")
    if manifest["runtime_manifest_sha256"] != current_runtime or entry["case_id"] != CASE:
        raise ValueError("Candidate not bound to current runtime and exact case")
    candidates = {"primary":{"construction":entry["construction"],
                             "construction_sha256":entry["construction_sha256"]}}
    candidates.update({candidate["id"]:candidate for candidate in entry["candidates"]})
    if set(candidates) != {"primary", "fallback1", "fallback2", "fallback3"}:
        raise ValueError("Candidate inventory incomplete")
    bound = {}
    for name, candidate in candidates.items():
        construction = HERE / candidate["construction"]
        if sha(construction) != candidate["construction_sha256"]:
            raise ValueError("Candidate construction changed: " + name)
        offline = FILES / (name + "-offline.log") if name != "primary" else HERE / "zero-exact-offline.log"
        compatibility = FILES / (name + "-compatibility.json")
        negative = FILES / (name + "-negative-analysis.log")
        analysis = FILES / (name + "-compatibility-analysis.log")
        saved = FILES / (name + "-saved-processing.json")
        receipt = json.loads(compatibility.read_text())
        later = json.loads(saved.read_text())
        if (receipt.get("passed") is not True or receipt.get("candidate_id") != name or
                receipt.get("case_id") != CASE or
                receipt.get("construction_sha256") != candidate["construction_sha256"] or
                receipt.get("runtime_manifest_sha256") != current_runtime):
            raise ValueError("Positive compatibility binding failed: " + name)
        if (receipt.get("negative_removed") != "lane_history.jsonl" or
                receipt.get("negative_error_contains") != "Missing required source: lane_history.jsonl" or
                receipt.get("negative_log_sha256") != sha(negative) or
                receipt.get("log_sha256") != sha(analysis)):
            raise ValueError("Negative source or analysis log binding failed: " + name)
        if (later.get("passed") is not True or later.get("recorded_only") is not True or
                later.get("candidate_id") != name or later.get("case_id") != CASE or
                later.get("analysis_revision",{}).get("construction_sha256") != candidate["construction_sha256"] or
                later.get("analysis_revision",{}).get("runtime_manifest_sha256") != current_runtime or
                later.get("originals_preserved") is not True):
            raise ValueError("Recorded-only saved binding failed: " + name)
        if "offline_passed" not in offline.read_text():
            raise ValueError("Offline construction receipt missing: " + name)
        bound[name] = {"construction_sha256":candidate["construction_sha256"],
                       "offline_log_sha256":sha(offline),
                       "compatibility_receipt_sha256":sha(compatibility),
                       "negative_log_sha256":sha(negative),
                       "saved_receipt_sha256":sha(saved)}
    comparison = HERE / "zero-exact-comparison-proof.json"
    if json.loads(comparison.read_text())["departure_frame"] != 101:
        raise ValueError("Controlled source comparison changed")
    report = {"format":"worker-c144550-zero-candidate-current-runtime-replay",
              "case_id":CASE,"manifest_sha256":sha(manifest_path),
              "runtime_manifest_sha256":current_runtime,
              "comparison_proof_sha256":sha(comparison),
              "candidates":bound,"selected_for_delivery":False,
              "physical_acceptance_claimed":False,"legal_acceptance_claimed":False}
    (HERE / "zero-exact-candidate-replay.json").write_text(json.dumps(report,indent=2)+"\n")
    return report


if __name__ == "__main__":
    result = prove()
    print(json.dumps({"candidate_count":len(result["candidates"]),
                      "manifest_sha256":result["manifest_sha256"]},sort_keys=True))
