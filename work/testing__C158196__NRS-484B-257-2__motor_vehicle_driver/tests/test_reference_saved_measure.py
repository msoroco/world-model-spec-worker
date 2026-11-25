import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location('c158196_reference_saved_measure',
                                              ROOT / 'reference_saved_measure.py')
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)
from stopping_reference import from_authored_site


class ReferenceSavedMeasureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.capture_path = Path(self.temp.name) / 'capture.json'

    def make_capture(self, site_name):
        site = ROOT / site_name
        reference = from_authored_site(site)
        center = reference['x_m'] - 2.0
        body = [[center + dx, dy] for dx, dy in
                ((-1, -1), (-1, 1), (1, -1), (1, 1),
                 (-1, -1), (-1, 1), (1, -1), (1, 1))]
        capture = {
            'format': 'worker-subsection-2-officer-native-capture',
            'case_id': 'testing__C158196__NRS-484B-257-2__motor_vehicle_driver__' +
                       {'stop_line': 'stop_line_reference',
                        'near_crosswalk': 'crosswalk_reference',
                        'nearest_view': 'nearest_view_reference'}[reference['kind']],
            'site_sha256': hashlib.sha256(site.read_bytes()).hexdigest(),
            'fixed_delta_seconds': 0.05, 'frame_count': 600,
            'rows': [{'frame_index': i, 'carla_frame': 101 + i,
                      'time_s': (i + 1) * 0.05,
                      'stopping_reference': reference,
                      'ego_body_vertices_xy_m': body,
                      'ego_front_x_m': center + 1.0,
                      'ego_speed_mps': 0.0}
                     for i in range(600)]}
        self.capture_path.write_text(json.dumps(capture, sort_keys=True) + '\n')
        return site, capture

    def test_line_crosswalk_and_nearest_view_source_order(self):
        for site_name, kind in (('line-reference-site.xodr', 'stop_line'),
                                ('crosswalk-reference-site.xodr', 'near_crosswalk'),
                                ('nearest-view-reference-site.xodr', 'nearest_view')):
            site, _ = self.make_capture(site_name)
            result = MEASURE.measure(self.capture_path, site)
            self.assertEqual(result['reference_kind'], kind)
            self.assertEqual(result['engineering_stop_sample_count'], 600)
            self.assertFalse(result['overshot_before_engineering_stop'])
            self.assertEqual(result['legal_stop_judgment'], 'unresolved')
            if kind == 'nearest_view':
                self.assertEqual(result['visibility_judgment'], 'unreviewed')

    def test_missing_body_and_changed_site_hash_rejected(self):
        site, capture = self.make_capture('line-reference-site.xodr')
        capture['rows'][17]['ego_body_vertices_xy_m'] = []
        self.capture_path.write_text(json.dumps(capture) + '\n')
        with self.assertRaisesRegex(ValueError, 'ego body missing'):
            MEASURE.measure(self.capture_path, site)
        capture['rows'][17]['ego_body_vertices_xy_m'] = capture['rows'][0]['ego_body_vertices_xy_m']
        capture['site_sha256'] = '0' * 64
        self.capture_path.write_text(json.dumps(capture) + '\n')
        with self.assertRaisesRegex(ValueError, 'Complete original'):
            MEASURE.measure(self.capture_path, site)

    def test_exact_case_cannot_claim_other_reference_kind(self):
        site, capture = self.make_capture('line-reference-site.xodr')
        capture['case_id'] = capture['case_id'].replace('stop_line_reference',
                                                      'crosswalk_reference')
        self.capture_path.write_text(json.dumps(capture) + '\n')
        with self.assertRaisesRegex(ValueError, 'case and authored site differ'):
            MEASURE.measure(self.capture_path, site)


if __name__ == '__main__':
    unittest.main()
