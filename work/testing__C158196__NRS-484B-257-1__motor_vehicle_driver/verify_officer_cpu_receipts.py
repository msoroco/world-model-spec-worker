"""Verify eight officer diagnostic CPU receipts against their exact constructions."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
manifest = json.loads((folder / "officer-pair-current-draft-manifest.json").read_text())
runtime_hash = digest(repo / "runtime" / "SOURCE-MANIFEST.json")
assert manifest["runtime_manifest_sha256"] == runtime_hash
count = 0
for case in manifest["cases"]:
    for candidate_id, entry in [("primary", case)] + [
        (candidate["id"], candidate) for candidate in case["candidates"]
    ]:
        construction_hash = entry["construction_sha256"]
        assert digest(folder / entry["construction"]) == construction_hash
        compatibility = entry["compatibility"]
        receipt_path = folder / compatibility["receipt"]
        assert digest(receipt_path) == compatibility["sha256"]
        receipt = json.loads(receipt_path.read_text())
        assert receipt["passed"] is True
        assert receipt["case_id"] == case["case_id"]
        assert receipt["candidate_id"] == candidate_id
        assert receipt["construction_sha256"] == construction_hash
        assert receipt["runtime_manifest_sha256"] == runtime_hash
        assert (folder / compatibility["log"]).is_file()
        assert (folder / compatibility["negative_log"]).is_file()
        saved = entry["post_capture"]
        saved_path = folder / saved["processing_receipt"]
        assert digest(saved_path) == saved["processing_sha256"]
        processing = json.loads(saved_path.read_text())
        assert processing["passed"] is True
        assert processing["recorded_only"] is True
        assert processing["originals_preserved"] is True
        assert processing["missing_evidence"] is False
        assert processing["physical_acceptance_claimed"] is False
        assert processing["legal_acceptance_claimed"] is False
        assert processing["case_id"] == case["case_id"]
        assert processing["candidate_id"] == candidate_id
        assert processing["analysis_revision"]["construction_sha256"] == construction_hash
        assert processing["analysis_revision"]["runtime_manifest_sha256"] == runtime_hash
        count += 1
assert count == 8
print(json.dumps({"runtime_manifest_sha256": runtime_hash, "verified_officer_variants": count}))
