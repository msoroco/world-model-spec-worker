import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('capture_c150153', ROOT / 'native_history_capture.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)
from test_parking import site
import parking


class Adapter:
    def __init__(self, site, case, first=4000, mutate=None):
        self.site, self.case, self.first, self.mutate = site, case, first, mutate
        self.index = 0

    def tick_and_sample(self):
        s, i = self.site, self.index
        self.index += 1
        body_west, body_east = parking.target_body_interval(s, self.case, 4.0)
        observed_activity = {'park': 'parked', 'stop': 'stopped',
                             'stand': 'standing'}[self.case.activity]
        row = {
            'case_id': self.case.id, 'original_frame': self.first + i,
            'time_s': 100.0 + i / 20, 'ego_id': 'native-ego-7',
            'fixture_id': 'native-elevator-9', 'frame_map_sha256': 'native-frame-map',
            'source_sha256': 'native-snapshot',
            'body_footprint_source_sha256': 'native-body',
            'body_west_x_m': body_west, 'body_east_x_m': body_east,
            'body_curb_gap_m': 0.3, 'ego_speed_mps': 0.0,
            'ego_position_m': [(body_west + body_east) / 2, s['curb_y_m'], 0.0],
            'ego_heading_deg': 0.0,
            'fixture_physically_present': True, 'activity_observation': observed_activity,
            'exception_kind': self.case.exception,
            'exception_source_sha256': None,
            'fixture_identity_sha256': s['fixture_identity_sha256'],
            'fixture_geometry_sha256': s['fixture_geometry_sha256'],
            'fixture_blueprint_sha256': s['fixture_blueprint_sha256'],
            'map_sha256': s['map_sha256'], 'site_sha256': s['site_sha256'],
            'camera_plan_sha256': s['camera_plan_sha256'],
            'municipal_jurisdiction_sha256': s['municipal_jurisdiction_sha256'],
            'sidewalk_sha256': s['sidewalk_sha256'], 'curb_sha256': s['curb_sha256'],
        }
        source_key = {
            'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
            'police_direction': 'police_direction_source_sha256',
            'traffic_device_direction': 'traffic_device_source_sha256',
        }.get(self.case.exception)
        if source_key:
            row['exception_source_sha256'] = s[source_key]
        if self.mutate is not None:
            self.mutate(i, row)
        return row


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.site = site()
        self.site['site_sha256'] = 'site-source'
        self.case = next(c for c in parking.CASES if c.id == 'east_inside')

    def test_900_original_frames_and_sealed_saved_audit(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'history.jsonl'
            proof = capture.capture_original_history(Adapter(self.site, self.case),
                                                     self.site, self.case, output)
            self.assertEqual(proof['first_original_frame'], 4000)
            self.assertEqual(proof['last_original_frame'], 4899)
            self.assertEqual(proof['frame_count'], 900)
            self.assertIsNone(proof['legal_judgment'])
            self.assertFalse(proof['physical_visibility_verified'])
            original = [__import__('json').loads(line) for line in output.read_text().splitlines()]
            measured = parking.measure_original_history(original, self.site, self.case)
            self.assertEqual(measured['frame_count'], 900)
            with self.assertRaisesRegex(ValueError, 'overwrite'):
                capture.capture_original_history(Adapter(self.site, self.case),
                                                 self.site, self.case, output)

    def test_source_and_frame_rejections_remove_incomplete_file(self):
        defects = [
            (lambda i, row: row.update(original_frame=9000) if i == 400 else None,
             'original frame'),
            (lambda i, row: row.update(fixture_geometry_sha256='other') if i == 400 else None,
             'site or fixture source'),
            (lambda i, row: row.update(time_s=222.0) if i == 400 else None,
             '20 Hz'),
            (lambda i, row: row.update(body_west_x_m=20.0) if i == 400 else None,
             'body footprint'),
        ]
        for mutate, error in defects:
            with self.subTest(error=error), tempfile.TemporaryDirectory() as temp:
                output = Path(temp) / 'history.jsonl'
                with self.assertRaisesRegex(ValueError, error):
                    capture.capture_original_history(Adapter(self.site, self.case, mutate=mutate),
                                                     self.site, self.case, output)
                self.assertFalse(output.exists())
                self.assertFalse(output.with_name(output.name + '.incomplete').exists())

    def test_exception_requires_original_direction_source(self):
        case = next(c for c in parking.CASES if c.id == 'front_police_exception')
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'history.jsonl'
            proof = capture.capture_original_history(Adapter(self.site, case),
                                                     self.site, case, output)
            self.assertEqual(proof['frame_count'], 900)
            def remove_source(i, row):
                if i == 400:
                    row['exception_source_sha256'] = None
            other = Path(temp) / 'other.jsonl'
            with self.assertRaisesRegex(ValueError, 'exception observation source'):
                capture.capture_original_history(Adapter(self.site, case, mutate=remove_source),
                                                 self.site, case, other)


if __name__ == '__main__':
    unittest.main()
