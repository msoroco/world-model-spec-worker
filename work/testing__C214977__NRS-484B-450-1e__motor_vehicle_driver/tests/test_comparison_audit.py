import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import comparison_audit as audit


class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.plan = json.loads((HERE / 'case-plan.json').read_text())

    def tearDown(self):
        self.tmp.cleanup()

    def seal(self, name, value):
        raw = (json.dumps(value, sort_keys=True) + '\n').encode()
        (self.root / name).write_bytes(raw)
        return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}

    def pair(self, comparison, mutate=None):
        ids = comparison['case_ids']
        sources = []
        for case_id in ids:
            case = next(c for c in self.plan['cases'] if c['case_id'] == case_id)
            source = {'format': 'crosswalk-comparison-source', 'case_id': case_id,
                      'law_id': self.plan['law_id'], 'actor': self.plan['actor'],
                      'cell_id': self.plan['cell_id'], 'map_name': 'Town',
                      'crosswalk_id': 'cw', 'site_source_sha256': 'site-hash',
                      'crosswalk_polygon': [[0, 0], [1, 0], [1, 1], [0, 1]],
                      'parking_route': [[-3, 0], [0, 0]],
                      'vehicle_source_sha256': 'vehicle-hash',
                      'vehicle_blueprint': 'sedan', 'camera_plan_sha256': 'camera-hash',
                      'original_frame_count': 900, 'source_format': 'native_original',
                      'action': case['action'], 'destination': case['destination'],
                      'exception': case['exception'],
                      'exception_sources': {'traffic_conflict': False, 'law': False,
                                            'police_direction': False, 'device_direction': False}}
            if case['exception'] != 'none':
                source['exception_sources'][case['exception']] = True
            sources.append(source)
        if mutate:
            mutate(sources)
        refs = {}
        for i, (case_id, source) in enumerate(zip(ids, sources)):
            source_ref = self.seal(f'source-{i}.json', source)
            delivery = {'format': 'crosswalk-reviewed-delivery', 'case_id': case_id,
                        'source_receipt': source_ref, 'delivery_accepted': True,
                        'physical_completion': True, 'full_video_decode': True,
                        'actual_pixels': True}
            refs[case_id] = self.seal(f'delivery-{i}.json', delivery)
        return refs

    def test_all_seven_planned_pairs(self):
        for comp in self.plan['comparisons']:
            with self.subTest(comp=comp['comparison_id']):
                refs = self.pair(comp)
                result = audit.audit(self.plan, comp['comparison_id'], self.root, refs)
                self.assertEqual(result['difference_checked'], comp['deliberate_differences'][0])
                self.assertIsNone(result['legal_judgment'])

    def test_missing_or_stale_delivery_rejected(self):
        comp = self.plan['comparisons'][0]
        refs = self.pair(comp)
        with self.assertRaisesRegex(audit.ComparisonError, 'both exact'):
            audit.audit(self.plan, comp['comparison_id'], self.root, {comp['case_ids'][0]: refs[comp['case_ids'][0]]})
        bad = dict(refs)
        bad[comp['case_ids'][1]] = {**bad[comp['case_ids'][1]], 'sha256': '0' * 64}
        with self.assertRaisesRegex(audit.ComparisonError, 'hash mismatch'):
            audit.audit(self.plan, comp['comparison_id'], self.root, bad)

    def test_missing_physical_acceptance_rejected(self):
        comp = self.plan['comparisons'][0]
        refs = self.pair(comp)
        path = self.root / refs[comp['case_ids'][1]]['path']
        delivery = json.loads(path.read_text())
        delivery['physical_completion'] = False
        refs[comp['case_ids'][1]] = self.seal(path.name, delivery)
        with self.assertRaisesRegex(audit.ComparisonError, 'physical proof missing'):
            audit.audit(self.plan, comp['comparison_id'], self.root, refs)

    def test_fixed_geometry_change_rejected(self):
        comp = self.plan['comparisons'][0]
        refs = self.pair(comp, lambda pair: pair[1].update(site_source_sha256='different'))
        with self.assertRaisesRegex(audit.ComparisonError, 'road_geometry'):
            audit.audit(self.plan, comp['comparison_id'], self.root, refs)

    def test_missing_exception_source_rejected(self):
        comp = next(c for c in self.plan['comparisons'] if c['comparison_id'] == 'device_exception')
        refs = self.pair(comp, lambda pair: pair[1]['exception_sources'].update(device_direction=False))
        with self.assertRaisesRegex(audit.ComparisonError, 'selected exception source absent'):
            audit.audit(self.plan, comp['comparison_id'], self.root, refs)


if __name__ == '__main__':
    unittest.main()
