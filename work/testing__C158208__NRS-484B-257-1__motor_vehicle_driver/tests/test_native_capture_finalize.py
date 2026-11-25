import sys
import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_capture_finalize import close_capture
import test_build_production_construction as production_fixtures


class CaptureFinalizeTests(unittest.TestCase):
    def test_refuses_diagnostic_capture_and_unrestored_world(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "original Native capture"):
                close_capture(root, {"source_kind": "synthetic_fixture",
                                     "world_restore": {"restored": True}})
            with self.assertRaisesRegex(ValueError, "verified world restore"):
                close_capture(root, {"source_kind": "original_capture",
                                     "world_restore": {"restored": False}})
            self.assertFalse((root / "capture-seal.json").exists())

    def test_original_finalizer_reopens_all_reviewed_sources(self):
        fixture = production_fixtures.ProductionConstructionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        root = fixture.root
        (root / "construction.json").write_text("{}\n")
        (root / "scene.json").write_text(json.dumps({"site_source": fixture.site_path.name}) + "\n")
        (root / "nearest-view-original-ticks.jsonl").write_text("{}\n" * 900)
        identity = {"case_id": ROOT.name + "__nearest_view_response",
                    "construction_sha256": hashlib.sha256((root / "construction.json").read_bytes()).hexdigest(),
                    "site_packet_sha256": hashlib.sha256(fixture.site_path.read_bytes()).hexdigest(),
                    "map_opendrive_sha256": fixture.site["map_opendrive_sha256"]}
        (root / "capture-identity.json").write_text(json.dumps(identity) + "\n")
        release = {"source_kind": "original_capture", "world_restore": {"restored": True},
                   "case_id": identity["case_id"], "frame_count": 900,
                   "capture_identity_sha256": hashlib.sha256(
                       (root / "capture-identity.json").read_bytes()).hexdigest()}
        (root / "yield_sign.txt").write_text("changed")
        with patch("native_capture_finalize.verify_seal", return_value={"samples": [{}] * 900}), \
             patch("native_capture_finalize.audit_camera_sources"):
            with self.assertRaisesRegex(ValueError, "yield_sign original source hash differs"):
                close_capture(root, release)


if __name__ == "__main__":
    unittest.main()
