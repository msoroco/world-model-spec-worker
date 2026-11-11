import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from headlamp_delivery_audit import audit_attempt, CAMERAS
from headlamp_finalizer import analyze
from headlamp_physical_outcome import check_physical_outcome
from test_headlamp_finalizer import sources, CASE


class HeadlampDeliveryAuditTests(unittest.TestCase):
    def test_recomputed_sources_and_complete_camera_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            for name in CAMERAS:
                (root / (name + '.mkv')).write_bytes(b'original camera placeholder')
            report = analyze(root)
            receipt = audit_attempt(root, report, decoder=lambda path, count, **kw: {'frames': count})
            self.assertEqual(receipt['frame_count'], 2)
            report['measurements']['headlamp_following_observation']['sources']['lighting_context.json'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'Stale or missing original source'):
                audit_attempt(root, report, decoder=lambda path, count, **kw: {'frames': count})
            report = analyze(root)
            with self.assertRaisesRegex(ValueError, 'Incomplete source camera decode'):
                audit_attempt(root, report, decoder=lambda path, count, **kw: {'frames': count - 1})

    def test_physical_review_requires_source_bound_pixels_and_premises(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sources(root)
            for name in CAMERAS:
                (root / (name + '.mkv')).write_bytes(name.encode())
            report = analyze(root)
            audit = audit_attempt(root, report, decoder=lambda path, count, **kw: {'frames': count})
            review = {'case_id': CASE, 'cameras': {name: {
                'source_sha256': audit['camera_decodes'][name]['source_sha256'],
                'reviewed_frames': 2, 'required_bodies_visible': True,
                'beam_region_visible': True} for name in CAMERAS},
                'civil_time_source_reviewed': True,
                'roadway_occupancy_source_reviewed': True,
                'beam_distribution_source_reviewed': True}
            self.assertIsNone(check_physical_outcome(audit, report, review, target_ft=299)['legal_conclusion'])
            review['cameras']['overview']['source_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'original-pixel review'):
                check_physical_outcome(audit, report, review, target_ft=299)
            review['cameras']['overview']['source_sha256'] = audit['camera_decodes']['overview']['source_sha256']
            review['civil_time_source_reviewed'] = False
            with self.assertRaisesRegex(ValueError, 'Civil-time premise'):
                check_physical_outcome(audit, report, review, target_ft=299)


if __name__ == '__main__':
    unittest.main()
