import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from production_delivery import audit_original
from delivery_audit import PREFIX
from native_observation import CAMERAS


class ProductionDeliveryTests(unittest.TestCase):
    def test_review_must_bind_original_sources_and_physical_observation(self):
        case_id = PREFIX + "midblock_unmarked_operating"
        measured = {
            "case_id": case_id, "crossing_frame_range": [100, 300],
            "source_observation_sha256": "a" * 64,
            "native_provenance": {"seal_sha256": "b" * 64},
            "encoded_camera_source_sha256": {name: name for name in CAMERAS},
            "source_sha256": {"map": "c" * 64},
            "marked_crosswalk_observed": False,
            "both_devices_operating_during_crossing": True,
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            review = {
                "format": "independent-original-pedestrian-review",
                "case_id": case_id, "source": "original_four_camera_video",
                "diagnostic_fixture": False, "reviewer": "independent reviewer",
                "method": "inspect original encoded camera views and joined crossing frames",
                "observation_sha256": "a" * 64,
                "native_seal_sha256": "b" * 64,
                "video_sha256": {name: name for name in CAMERAS},
                "site_source_sha256": {"map": "c" * 64},
                "reviewed_frame_ids": [0, 100, 300, 899],
                "walker_visible_in_original_views": True,
                "crossing_completed_in_original_views": True,
                "both_highway_banks_visible": True,
                "both_devices_visible": True,
                "full_original_video_reviewed": True,
                "marking_observed": False,
                "both_devices_operating_during_crossing": True,
                "reviewed_camera_names": list(CAMERAS),
            }
            path = root / "independent-physical-review.json"
            path.write_text(json.dumps(review) + "\n")
            ref = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
            with patch("production_delivery.inspect", return_value=measured) as original:
                result = audit_original(root, case_id, ref)
                self.assertTrue(result["actual_pixels"])
                self.assertTrue(result["physical_completion"])
                self.assertIsNone(result["legal_verdict"])
                self.assertEqual(original.call_args.kwargs, {"diagnostic": False})
                review["reviewed_frame_ids"] = [0, 100, 899]
                path.write_text(json.dumps(review) + "\n")
                bad_ref = {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                with self.assertRaisesRegex(ValueError, "not bound"):
                    audit_original(root, case_id, bad_ref)
                with self.assertRaisesRegex(ValueError, "hash mismatch"):
                    audit_original(root, case_id, ref)


if __name__ == "__main__":
    unittest.main()
