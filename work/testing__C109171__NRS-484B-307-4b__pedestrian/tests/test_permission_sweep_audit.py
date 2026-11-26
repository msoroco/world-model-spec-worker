import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from native_scene import SourceError
from permission_applicability import PROVISIONS
from permission_sweep_audit import audit
from saved_measurement import ASSIGNMENT


class PermissionSweepAuditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd() / '.runtime-work')
        self.root = Path(self.tmp.name)
        self.route = [[-2, 1], [-1, 1], [1, 1], [3, 1]]
        self.boundary = [[0, 0], [4, 0], [4, 4], [0, 4]]
        map_ref = self.put('map.json', {'route_id': 'crossing-1', 'pedestrian_route_xy': self.route,
                                        'highway_boundary_xy': self.boundary})
        head_ref = self.put('head.json', {'head_id': 'head-1', 'official': True,
                                          'sole_green_arrow_aspect': 'green-left-arrow'})
        device_ref = self.put('device.json', {'device_id': 'ped-1', 'governs_route_id': 'crossing-1'})
        self.site_ref = self.put('site.json', {
            'source_kind': 'native_original', 'cell_id': 'C109171', 'actor': 'pedestrian',
            'original_sources': [map_ref, head_ref, device_ref], 'map_source_path': 'map.json',
            'vehicle_signal_source_path': 'head.json', 'pedestrian_device_source_path': 'device.json',
            'official_vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
            'pedestrian_route_id': 'crossing-1', 'pedestrian_device_governs_route': True,
            'pedestrian_faces_vehicle_head': True, 'sole_green_arrow_aspect': 'green-left-arrow',
            'pedestrian_route_xy': self.route, 'highway_boundary_xy': self.boundary})
        self.review = {
            'format': 'c109171-permission-applicability-review-v1',
            'site_sha256': self.site_ref['sha256'], 'cell_id': 'C109171',
            'pedestrian_route_id': 'crossing-1', 'pedestrian_device_id': 'ped-1',
            'vehicle_head_id': 'head-1', 'permission_at_entry': None,
            'provisions': [{'provision_id': provision, 'applicability': 'unresolved',
                            'reason': 'Synthetic source-shaped review; original legal review remains pending',
                            'law_source': self.put(f'law-{i}.txt', provision + ': synthetic source text'),
                            'device_source': device_ref} for i, provision in enumerate(PROVISIONS)]}

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name, value):
        path = self.root / name
        path.write_text(value if isinstance(value, str) else json.dumps(value), encoding='utf-8')
        return {'path': name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def events(self, enter, walk, frames=4, entry_frame=2):
        points = ([-2] * max(1, entry_frame - 1) + [-1] +
                  ([1] * (frames - entry_frame) if enter else [-0.5] * (frames - entry_frame)))
        return [{'frame': i, 'sim_time_seconds': i * 0.05,
                 'vehicle_head_id': 'head-1', 'pedestrian_device_id': 'ped-1',
                 'vehicle_head_lit_aspects': ['green-left-arrow'],
                 'pedestrian_facing_vehicle_head': True,
                 'pedestrian_device_indication': 'WALK' if walk and i >= 1 else 'DONT_WALK',
                 'pedestrian_xy': [x, 1]} for i, x in enumerate(points)]

    def run_audit(self, suffix, enter, walk, review=None):
        review_ref = self.put('review.json', self.review if review is None else review)
        event_ref = self.put('events.json', self.events(enter, walk))
        return audit(self.root, ASSIGNMENT + '__' + suffix, self.site_ref, review_ref, event_ref, 4)

    def test_all_four_engineering_configurations_without_permission_verdict(self):
        for suffix, enter, walk in [('arrow_wait', False, False),
                                     ('arrow_early_entry', True, False),
                                     ('arrow_walk_entry', True, True),
                                     ('arrow_walk_wait', False, True)]:
            with self.subTest(suffix=suffix):
                result = self.run_audit(suffix, enter, walk)
                self.assertEqual(result['provision_ids'], list(PROVISIONS))
                self.assertEqual(result['unresolved_provisions'], list(PROVISIONS))
                self.assertIsNone(result['permission_at_entry'])
                self.assertIsNone(result['legal_verdict'])
                self.assertFalse(result['physical_acceptance'])

    def test_rejects_missing_and_changed_original_device_source(self):
        missing = self.root / 'device.json'
        missing.unlink()
        with self.assertRaisesRegex(SourceError, 'missing'):
            self.run_audit('arrow_wait', False, False)
        missing.write_text('{}', encoding='utf-8')
        with self.assertRaisesRegex(SourceError, 'hash'):
            self.run_audit('arrow_wait', False, False)

    def test_rejects_missing_provision_and_premature_permission(self):
        review = json.loads(json.dumps(self.review))
        review['provisions'].pop()
        with self.assertRaisesRegex(SourceError, 'all four'):
            self.run_audit('arrow_wait', False, False, review)
        review = json.loads(json.dumps(self.review))
        review['permission_at_entry'] = True
        with self.assertRaisesRegex(SourceError, 'before capture'):
            self.run_audit('arrow_wait', False, False, review)

    def test_rejects_wrong_exact_case_and_unrealized_entry(self):
        with self.assertRaisesRegex(SourceError, 'entry behavior'):
            self.run_audit('arrow_wait', True, False)
        with self.assertRaisesRegex(SourceError, 'unknown exact'):
            audit(self.root, ASSIGNMENT + '__not_selected', self.site_ref, {}, {}, 4)

    def test_four_cited_provision_focus_points(self):
        review_ref = self.put('review.json', self.review)
        event_ref = self.put('events.json', self.events(True, True, 100, 90))
        for index, provision in enumerate(PROVISIONS):
            case_id = ASSIGNMENT + '__permission_applicability-' + str(index).zfill(4)
            with self.subTest(provision=provision):
                result = audit(self.root, case_id, self.site_ref, review_ref,
                               event_ref, 100, provision)
                self.assertEqual(result['focus_provision_id'], provision)
                self.assertEqual(result['focus_applicability'], 'unresolved')
                self.assertIsNone(result['permission_at_entry'])
                with self.assertRaisesRegex(SourceError, 'focused provision'):
                    audit(self.root, case_id, self.site_ref, review_ref,
                          event_ref, 100, PROVISIONS[(index + 1) % 4])


if __name__ == '__main__':
    unittest.main()
