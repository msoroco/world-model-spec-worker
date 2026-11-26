"""Structural review joins use synthetic sources; no physical acceptance claim."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from physical_review import OBSERVATIONS, review
from test_independent_delivery_audit import DeliveryAuditTests, sha


class PhysicalReviewTests(unittest.TestCase):
    def fixture(self, root):
        attempt, site, sources, seal = DeliveryAuditTests().fixture(root)
        packet = {
            "format": "sidewalk-elevator-original-pixel-review",
            "reviewer": "independent reviewer", "citation": "synthetic protocol test",
            "case_id": seal["case_id"], "site_packet_sha256": sha(site),
            "source_hashes": seal["sources"],
            "observations": {name: {
                "observed": True, "camera": "overview", "original_frame": 4100,
                "camera_sha256": seal["sources"]["overview.mkv"],
                "note": "synthetic structural test only", "reviewer": "independent reviewer",
            } for name in OBSERVATIONS},
        }
        claim = Path(root) / "review.json"
        claim.write_text(json.dumps(packet) + "\n")
        delivery = {
            "case_id": seal["case_id"], "site_packet_sha256": sha(site),
            "source_hashes": seal["sources"],
        }
        return attempt, site, sources, claim, packet, delivery

    def test_complete_original_review_binding_and_negative_sources(self):
        scratch = Path('.runtime-work/c150153-physical-review-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, claim, packet, delivery = self.fixture(temp)
            with self.assertRaisesRegex(ValueError, 'outside worker repository'):
                review(attempt, site, sources, claim, sha(claim))
            with patch('physical_review.audit', return_value=delivery):
                result = review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)
                self.assertEqual(result['frame_count'], 900)
                self.assertTrue(result['all_required_observations'])
                self.assertIsNone(result['legal_judgment'])
                with self.assertRaisesRegex(ValueError, 'hash differs'):
                    review(attempt, site, sources, claim, '0' * 64, diagnostic_fixture=True)
                packet['observations']['camera_visibility']['observed'] = False
                claim.write_text(json.dumps(packet) + '\n')
                with self.assertRaisesRegex(ValueError, 'required original physical observation absent'):
                    review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)
                packet['observations']['camera_visibility']['observed'] = True
                packet['observations']['camera_visibility']['camera_sha256'] = '0' * 64
                claim.write_text(json.dumps(packet) + '\n')
                with self.assertRaisesRegex(ValueError, 'camera source changed'):
                    review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)
                packet['observations']['camera_visibility']['camera_sha256'] = delivery['source_hashes']['overview.mkv']
                packet['observations']['camera_visibility']['original_frame'] = 100
                claim.write_text(json.dumps(packet) + '\n')
                with self.assertRaisesRegex(ValueError, 'frame or camera invalid'):
                    review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)

    def test_missing_review_observation_and_wrong_region(self):
        scratch = Path('.runtime-work/c150153-physical-review-tests')
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as temp:
            attempt, site, sources, claim, packet, delivery = self.fixture(temp)
            del packet['observations']['sidewalk_elevator_identity']
            claim.write_text(json.dumps(packet) + '\n')
            with patch('physical_review.audit', return_value=delivery):
                with self.assertRaisesRegex(ValueError, 'observations incomplete'):
                    review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)
            packet['observations']['sidewalk_elevator_identity'] = dict(
                packet['observations']['elevator_front_and_side_edges'])
            claim.write_text(json.dumps(packet) + '\n')
            bad = dict(delivery, case_id=delivery['case_id'].replace('west_inside', 'front_park'))
            with patch('physical_review.audit', return_value=bad):
                with self.assertRaisesRegex(ValueError, 'source binding differs'):
                    review(attempt, site, sources, claim, sha(claim), diagnostic_fixture=True)


if __name__ == '__main__':
    unittest.main()
