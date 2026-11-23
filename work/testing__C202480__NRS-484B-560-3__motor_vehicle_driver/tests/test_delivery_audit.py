"""Check the assembled original-source delivery join with diagnostic receipts."""

import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit
from geometry_audit import audit as geometry_audit
from native_camera import VIEWS
from saved_measurement import finalize_attempt, sha
import test_saved_measurement as saved_fixture


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        fixture = saved_fixture.SavedMeasurementTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.attempt = fixture.attempt
        finalize_attempt(self.attempt, self.attempt / "analysis-report.json")
        (self.attempt / "geometry-audit.json").write_text(
            json.dumps(geometry_audit(self.attempt)))
        mapping_hash = sha(self.attempt / "video_frames.jsonl")
        media_hash = sha(self.attempt / "media-receipt.json")
        receipts = {}
        for name, width, height in VIEWS:
            path = self.attempt / ("source-decode-" + name + ".json")
            path.write_text(json.dumps({"frames": 900, "dimensions": [width, height],
                                        "video_sha256": sha(self.attempt / (name + ".mkv")),
                                        "mapping_sha256": mapping_hash}))
            receipts[name] = {"path": path.name, "sha256": sha(path)}
        (self.attempt / "source-decode-receipt.json").write_text(json.dumps({
            "format": "c202480-four-original-source-decode-v1", "frames": 900,
            "frame_map_sha256": mapping_hash, "media_receipt_sha256": media_hash,
            "receipts": receipts, "sampled_pixels_nonuniform": True,
            "feature_visibility_verified": False, "physical_acceptance_claimed": False}))

    def verify(self, video, receipt, count, mapping_hash, checker_hash):
        self.assertEqual(count, 900)
        self.assertEqual(len(checker_hash), 64)
        value = json.loads(receipt.read_text())
        self.assertEqual(value["mapping_sha256"], mapping_hash)
        self.assertEqual(value["video_sha256"], sha(video))
        return value

    def test_all_four_receipts_join_saved_result_and_geometry(self):
        result = audit(self.attempt, decode_verifier=self.verify)
        self.assertEqual(len(result["source_decode_receipts_sha256"]), 4)
        self.assertFalse(result["feature_visibility_verified"])
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_falsified_saved_result_rejected(self):
        path = self.attempt / "result.json"
        value = json.loads(path.read_text())
        value["maneuver_completed"] = True
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, "saved analysis differs"):
            audit(self.attempt, decode_verifier=self.verify)

    def test_missing_decode_receipt_rejected(self):
        (self.attempt / "source-decode-overview.json").unlink()
        with self.assertRaises((FileNotFoundError, ValueError)):
            audit(self.attempt, decode_verifier=self.verify)


if __name__ == "__main__":
    unittest.main()
