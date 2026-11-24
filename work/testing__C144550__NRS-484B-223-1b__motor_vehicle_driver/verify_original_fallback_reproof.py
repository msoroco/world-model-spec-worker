"""Check all fifteen original fallbacks against current-runtime CPU receipts."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
manifest = json.loads((HERE / "execution-manifest.json").read_text())
runtime_sha = hashlib.sha256((ROOT / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest()
assert manifest["runtime_manifest_sha256"] == runtime_sha


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


count = 0
for entry in manifest["cases"][:5]:
    assert len(entry["candidates"]) == 3
    for candidate in entry["candidates"]:
        cid = candidate["id"]
        spec = candidate["compatibility"]
        assert "-current-" in spec["receipt"]
        receipt_path = HERE / spec["receipt"]
        receipt = json.loads(receipt_path.read_text())
        assert sha(receipt_path) == spec["sha256"]
        assert (receipt["format"] == "worker-package-compatibility" and receipt["passed"] is True
                and receipt["case_id"] == entry["case_id"] and receipt["candidate_id"] == cid
                and receipt["construction_sha256"] == candidate["construction_sha256"]
                and receipt["runtime_manifest_sha256"] == runtime_sha)
        assert {"selected_measurements", "negative_case_source", "lean_decoder", "final_decode"} <= set(receipt["checks"])
        assert sha(HERE / spec["log"]) == receipt["log_sha256"]
        assert sha(HERE / spec["negative_log"]) == receipt["negative_log_sha256"]
        assert receipt["negative_error_contains"] in (HERE / spec["negative_log"]).read_text()
        post = candidate["post_capture"]
        saved_path = HERE / post["processing_receipt"]
        saved = json.loads(saved_path.read_text())
        assert sha(saved_path) == post["processing_sha256"] == post["test_log_sha256"]
        assert (post["recorded_only"] is True and post["test_exit_code"] == 0
                and saved["format"] == "worker-saved-processing" and saved["passed"] is True
                and saved["recorded_only"] is True and saved["case_id"] == entry["case_id"]
                and saved["candidate_id"] == cid and saved["originals_preserved"] is True
                and saved["analysis_revision"]["construction_sha256"] == candidate["construction_sha256"]
                and saved["analysis_revision"]["runtime_manifest_sha256"] == runtime_sha)
        count += 1
        print("PASS", entry["case_id"], cid)
assert count == 15
print("All 15 original fallbacks have current-runtime source-bound compatibility and recorded-only saved proofs")
