import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_scene import SourceError
from permission_applicability import PROVISIONS, validate
from independent_cpu_delivery import audit as audit_delivery


class PermissionReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work')
        self.root = Path(self.tmp.name)

        def put(name, value):
            path = self.root / name
            path.write_text(value if isinstance(value, str) else json.dumps(value))
            return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

        self.put = put
        map_ref = put('map.json', {'route_id': 'crossing-1',
                   'pedestrian_route_xy': [[-2, 1], [-1, 1], [1, 1]],
                   'highway_boundary_xy': [[0, 0], [4, 0], [4, 4], [0, 4]]})
        head_ref = put('head.json', {'head_id': 'head-1', 'official': True,
                       'sole_green_arrow_aspect': 'green-left-arrow'})
        device_ref = put('device.json', {'device_id': 'ped-1',
                         'governs_route_id': 'crossing-1'})
        self.site_ref = put('site.json', {
            'cell_id': 'C109171', 'actor': 'pedestrian',
            'original_sources': [map_ref, head_ref, device_ref],
            'map_source_path': 'map.json', 'vehicle_signal_source_path': 'head.json',
            'pedestrian_device_source_path': 'device.json',
            'official_vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
            'pedestrian_route_id': 'crossing-1', 'pedestrian_device_governs_route': True,
            'pedestrian_faces_vehicle_head': True,
            'sole_green_arrow_aspect': 'green-left-arrow',
            'pedestrian_route_xy': [[-2, 1], [-1, 1], [1, 1]],
            'highway_boundary_xy': [[0, 0], [4, 0], [4, 4], [0, 4]]})
        self.review = {'format': 'c109171-permission-applicability-review-v1',
                       'site_sha256': self.site_ref['sha256'], 'cell_id': 'C109171',
                       'pedestrian_route_id': 'crossing-1', 'pedestrian_device_id': 'ped-1',
                       'vehicle_head_id': 'head-1', 'permission_at_entry': None,
                       'provisions': [
                           {'provision_id': provision, 'applicability': 'unresolved',
                            'reason': 'Synthetic source, no legal conclusion',
                            'law_source': put(f'law-{i}.txt', provision + ': fixture text'),
                            'device_source': device_ref}
                           for i, provision in enumerate(PROVISIONS)]}

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return validate(self.root, self.site_ref, self.put('review.json', self.review))

    def test_four_unresolved_provisions_are_retained_without_verdict(self):
        receipt = self.check()
        self.assertEqual(receipt['unresolved_provisions'], list(PROVISIONS))
        self.assertIsNone(receipt['legal_verdict'])

    def test_rejects_missing_provision(self):
        self.review['provisions'].pop()
        with self.assertRaisesRegex(SourceError, 'all four'):
            self.check()

    def test_rejects_conflated_device(self):
        self.review['pedestrian_device_id'] = 'head-1'
        with self.assertRaisesRegex(SourceError, 'bind original site'):
            self.check()

    def test_rejects_changed_original_device(self):
        self.review['provisions'][0]['device_source'] = self.put('different.json', '{}')
        with self.assertRaisesRegex(SourceError, 'not the original governing device'):
            self.check()

    def test_rejects_unsourced_applicability(self):
        self.review['provisions'][0]['law_source']['sha256'] = '0' * 64
        with self.assertRaisesRegex(SourceError, 'hash differs'):
            self.check()

    def test_rejects_premature_permission_claim(self):
        self.review['permission_at_entry'] = True
        with self.assertRaisesRegex(SourceError, 'before capture'):
            self.check()

    def test_production_delivery_rejects_absent_review(self):
        self.put('pedestrian-source.json', {'case_id': 'case',
                 'diagnostic_fixture': False, 'site_ref': self.site_ref})
        with self.assertRaisesRegex(ValueError, 'permission review missing'):
            audit_delivery(self.root, 'case')


if __name__ == '__main__':
    unittest.main()
