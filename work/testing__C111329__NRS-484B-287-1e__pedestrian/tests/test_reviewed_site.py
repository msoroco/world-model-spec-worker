import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from reviewed_site import validate_reviewed_site


class ReviewedSiteTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111329-reviewed-site-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.site = {
            'coordinate_frame': 'map_xy_m',
            'corners_clockwise': [[0, 0], [10, 0], [10, 10], [0, 10]],
            'pedestrian_route': [[0, 0], [5, 5], [10, 10]],
            'governing_device': {'id': 'ped-1', 'authority_record_id': 'order-1',
                                 'instruction_record_id': 'order-1-diagonal',
                                 'placement_record_id': 'survey-1',
                                 'governs': 'pedestrian_diagonal',
                                 'diagonal_authorized': True},
            'observed_device_ids': ['ped-1'],
            'exception_484b_290_review': 'unresolved', 'sources': {}}
        map_data = '<OpenDRIVE><road><planView><geometry s="0" x="0" y="0" hdg="0" length="10"/></planView></road></OpenDRIVE>'
        self._seal('map', map_data)
        self._seal('corner_survey', {'cell_id': 'C111329',
            'map_sha256': self.site['sources']['map']['sha256'],
            'corners_clockwise': self.site['corners_clockwise'],
            'route_xy': self.site['pedestrian_route'],
            'survey_method': 'diagnostic shape test', 'reviewer': 'fixture'})
        self._seal('authorization', {'cell_id': 'C111329', 'record_id': 'order-1',
            'movement': 'pedestrian_diagonal', 'device_id': 'ped-1',
            'authorized': True, 'issuing_authority': 'fixture',
            'original_document_ref': 'fixture-only', 'reviewer': 'fixture'})
        self._seal('device_inventory', {'cell_id': 'C111329', 'device_id': 'ped-1',
            'movement': 'pedestrian_diagonal', 'instruction_record_id': 'order-1-diagonal',
            'placement_record_id': 'survey-1', 'authorization_record_id': 'order-1',
            'original_device_observation_ref': 'fixture-only', 'reviewer': 'fixture'})
        self._seal('exception_review', {'statute': 'NRS 484B.290',
            'review_state': 'unresolved', 'source_ref': 'fixture-only', 'reviewer': 'fixture'})

    def _seal(self, name, content):
        path = self.root / (name + ('.xodr' if name == 'map' else '.json'))
        path.write_text(content if isinstance(content, str) else json.dumps(content))
        self.site['sources'][name] = {'path': str(path),
                                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def test_source_cross_joins_keep_official_status_pending(self):
        result = validate_reviewed_site(self.site)
        self.assertEqual(result['official_status'], 'source_review_required')
        self.assertEqual(result['physical_realization'], 'unconfirmed')

    def test_wrong_movement_and_stale_original_source_rejected(self):
        path = Path(self.site['sources']['authorization']['path'])
        authority = json.loads(path.read_text())
        authority['movement'] = 'motor_vehicle'
        self._seal('authorization', authority)
        with self.assertRaisesRegex(ValueError, 'official diagonal authorization'):
            validate_reviewed_site(self.site)
        path.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
            validate_reviewed_site(self.site)


if __name__ == '__main__':
    unittest.main()
