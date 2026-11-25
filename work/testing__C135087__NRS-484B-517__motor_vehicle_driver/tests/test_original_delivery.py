"""Focused negatives for production original-attempt delivery review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from audit_original_delivery import _review, audit
from stand import SourceError


class OriginalDeliveryTest(unittest.TestCase):
    def test_review_reference_rejects_missing_and_changed_bytes(self):
        scratch = HERE.parents[1] / ".runtime-work"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            packet = root / "review.json"
            packet.write_text('{"reviewer":"independent"}\n')
            ref = {"path": "review.json", "sha256": hashlib.sha256(packet.read_bytes()).hexdigest()}
            self.assertEqual(_review(root, ref)["reviewer"], "independent")
            packet.write_text('{"reviewer":"changed"}\n')
            with self.assertRaisesRegex(SourceError, "hash changed"):
                _review(root, ref)
            with self.assertRaisesRegex(SourceError, "escapes attempt"):
                _review(root, {"path": "../review.json", "sha256": ref["sha256"]})

    def test_missing_original_candidate_rejected_before_review(self):
        scratch = HERE.parents[1] / ".runtime-work"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            manifest = json.loads((HERE / "execution-manifest.json").read_text())
            cid = manifest["cases"][0]["case_id"]
            with self.assertRaises(FileNotFoundError):
                audit(cid, root, {"path": "review.json", "sha256": "0" * 64})

    def test_review_binding_and_physical_flags(self):
        scratch = HERE.parents[1] / ".runtime-work"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            manifest_path = HERE / "execution-manifest.json"
            manifest = json.loads(manifest_path.read_text())
            entry = manifest["cases"][0]
            cid = entry["case_id"]
            selection = {"format": "worker-candidate-selection", "candidate_id": "primary",
                         "case_id": cid, "construction_sha256": entry["construction_sha256"],
                         "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
            (root / "candidate-selection.json").write_text(json.dumps(selection) + "\n")
            for name in ("site-original.json", "vehicle-original.json", "overview.mkv",
                         "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
                (root / name).write_text(name + "\n")
            sha = lambda name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            review = {"source": "independent_original_site_vehicle_video_review",
                      "reviewer": "independent", "case_id": cid,
                      "reviewed_site_sha256": sha("site-original.json"),
                      "reviewed_vehicle_sha256": sha("vehicle-original.json"),
                      "official_stand_designation_source_reviewed": True,
                      "stand_sign_source_reviewed": True,
                      "subject_passenger_vehicle_source_reviewed": True,
                      "entrant_taxicab_source_reviewed": True,
                      "video_sha256": {view: sha(view + ".mkv") for view in
                                       ("overview", "approach", "reference_corner", "driver_reference")},
                      "reviewed_frame_ids": [0, 450, 899],
                      "subject_and_entrant_visible": True,
                      "passenger_loading_visible": True,
                      "stand_and_sign_visible": True,
                      "physical_motion_completed": True}
            packet = root / "review.json"
            packet.write_text(json.dumps(review) + "\n")
            ref = {"path": packet.name, "sha256": sha(packet.name)}
            measured = {"case_id": cid, "measurements": {"source_frame_count": 900},
                        "attempt_source_sha256": "a" * 64, "decoded_camera_frames": 3600}
            with patch("audit_original_delivery.extract", return_value=measured) as source_audit:
                receipt = audit(cid, root, ref)
                self.assertEqual(receipt["decoded_camera_frames"], 3600)
                self.assertFalse(receipt["legal_verdict_claimed"])
                source_audit.assert_called_once_with(root, review["reviewed_site_sha256"],
                                                     review["reviewed_vehicle_sha256"])
                review["passenger_loading_visible"] = False
                packet.write_text(json.dumps(review) + "\n")
                ref["sha256"] = sha(packet.name)
                with self.assertRaisesRegex(SourceError, "physical completion or pixel review missing"):
                    audit(cid, root, ref)


if __name__ == "__main__":
    unittest.main()
