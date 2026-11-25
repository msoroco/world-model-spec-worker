import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from native_crossing import SourceError
from reviewed_site_preflight import review


class ReviewedSitePreflightTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / '.runtime-work/c111125-site-preflight-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sources = [
            self.write('map.json', {
                'public_highway': True,
                'highway_polygon_xy': [[0, 0], [10, 0], [10, 10], [0, 10]],
                'crosswalk_polygon_xy': [[0, 4], [10, 4], [10, 6], [0, 6]],
                'crosswalk_kind': 'marked', 'crosswalk_qualifies': True}),
            self.write('head.json', {
                'official': True, 'control': 'traffic_light', 'head_id': 'head1',
                'pedestrian_faces_head': True}),
            self.write('devices.json', {
                'other_device_id': 'ped1', 'inventory_complete': True,
                'route_applicability': {
                    'route_id': 'route1', 'device_id': 'ped1', 'applies': True,
                    'law_refs': ['NRS-484B-283-1d1'],
                    'review_basis': 'Original device inventory and route review'}}),
        ]
        self.site = {
            'cell_id': 'C111125', 'actor': 'pedestrian',
            'diagnostic_fixture': False, 'reviewed_original_site': True,
            'review_source_id': 'fixture-review-only',
            'original_sources': self.sources,
            'map_source_path': 'map.json', 'signal_source_path': 'head.json',
            'device_inventory_source_path': 'devices.json',
            'official_signal_head_id': 'head1', 'pedestrian_faces_head': True,
            'public_highway_source_assertion': True,
            'crosswalk_qualification_source_assertion': True,
            'crosswalk_kind': 'marked',
            'highway_polygon_xy': [[0, 0], [10, 0], [10, 10], [0, 10]],
            'crosswalk_polygon_xy': [[0, 4], [10, 4], [10, 6], [0, 6]],
            'pedestrian_route_id': 'route1',
            'pedestrian_route_xy': [[-2, 5], [2, 5], [11, 5]],
            'other_device_id': 'ped1',
        }

    def write(self, name, obj):
        path = self.root / name
        path.write_text(json.dumps(obj, sort_keys=True) + '\n')
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def site_path(self):
        path = self.root / 'site.json'
        path.write_text(json.dumps(self.site, sort_keys=True) + '\n')
        return path

    def test_source_bound_route_applicability(self):
        result = review(self.site_path())
        self.assertTrue(result['device_applies_to_route'])
        self.assertEqual(result['referenced_provisions'], ['NRS-484B-283-1d1'])
        self.assertFalse(result['physical_acceptance'])
        self.assertIsNone(result['legal_verdict'])

    def test_missing_applicability_rejected(self):
        device = json.loads((self.root / 'devices.json').read_text())
        del device['route_applicability']
        self.sources[2] = self.write('devices.json', device)
        with self.assertRaisesRegex(SourceError, 'route applicability missing'):
            review(self.site_path())

    def test_route_mismatch_and_missing_citation_rejected(self):
        device = json.loads((self.root / 'devices.json').read_text())
        device['route_applicability']['route_id'] = 'different'
        self.sources[2] = self.write('devices.json', device)
        with self.assertRaisesRegex(SourceError, 'route differs'):
            review(self.site_path())
        device['route_applicability']['route_id'] = 'route1'
        device['route_applicability']['law_refs'] = []
        self.sources[2] = self.write('devices.json', device)
        with self.assertRaisesRegex(SourceError, 'lacks cited'):
            review(self.site_path())

    def test_stale_source_and_diagnostic_site_rejected(self):
        self.site['diagnostic_fixture'] = True
        with self.assertRaisesRegex(SourceError, 'reviewed original site'):
            review(self.site_path())
        self.site['diagnostic_fixture'] = False
        (self.root / 'devices.json').write_text('{}\n')
        with self.assertRaisesRegex(SourceError, 'source hash mismatch'):
            review(self.site_path())

    def test_each_device_case_requires_its_source_cited_provision(self):
        prefix = ROOT.name + '__'
        self.assertEqual(review(self.site_path(), prefix + 'walk_cross')['case_id'],
                         prefix + 'walk_cross')
        for suffix in ('flashing_countdown_cross', 'flashing_no_countdown_wait',
                       'walk_then_flash_continue', 'walk_then_steady_continue'):
            with self.assertRaisesRegex(SourceError, 'missing case provision'):
                review(self.site_path(), prefix + suffix)
        device = json.loads((self.root / 'devices.json').read_text())
        device['route_applicability']['law_refs'] = [
            'NRS-484B-283-1d1', 'NRS-484B-283-1d2',
            'NRS-484B-283-1d3', 'NRS-484B-283-1d4']
        self.sources[2] = self.write('devices.json', device)
        for suffix in ('flashing_countdown_cross', 'flashing_no_countdown_wait',
                       'walk_then_flash_continue', 'walk_then_steady_continue'):
            self.assertEqual(review(self.site_path(), prefix + suffix)['case_id'],
                             prefix + suffix)


if __name__ == '__main__':
    unittest.main()
