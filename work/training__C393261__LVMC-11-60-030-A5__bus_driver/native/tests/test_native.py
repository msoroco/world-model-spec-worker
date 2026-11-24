import json
import tempfile
import unittest
from pathlib import Path
from geometry import check as geometry_check, open_drive
from runner import check as runner_check, survey
from measure import measure

class FakeCarla:
    class LaneType:
        Parking = 'parking'
    class Location:
        def __init__(self, x, y, z):
            self.x, self.y, self.z = x, y, z

class FakeWaypoint:
    def __init__(self, x, y):
        self.road_id = 1
        self.lane_id = -2
        self.transform = type('T', (), {'location': FakeCarla.Location(x, y, 0)})()

class FakeMap:
    def __init__(self, wrong=False):
        self.wrong = wrong
    def to_opendrive(self):
        return open_drive().replace('BUS ROUTE TERMINUS', 'OTHER MARKER') if self.wrong else open_drive()
    def get_waypoint(self, location, project_to_road, lane_type):
        return FakeWaypoint(location.x, location.y)

class FakeWorld:
    def __init__(self, wrong=False):
        self.mapping = FakeMap(wrong)
    def get_map(self):
        return self.mapping

class NativeDraft(unittest.TestCase):
    def test_geometry_and_survey(self):
        self.assertFalse(geometry_check()['sign_declares_duration'])
        self.assertEqual(len(survey(FakeWorld(), FakeCarla)['parking_lane_samples']), 4)
        with self.assertRaisesRegex(RuntimeError, 'terminus marker'):
            survey(FakeWorld(True), FakeCarla)
    def test_capture_plan(self):
        plan = runner_check()
        self.assertEqual(plan['frames'], 600)
        self.assertEqual(len(plan['cameras']), 4)
    def test_source_bound_duration_and_missing_designation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            context = {'zone_x_m': [-2.0, 20.0], 'parking_lane_id': -2, 'native_survey': survey(FakeWorld(), FakeCarla), 'designation_verified': False, 'designated_period_s': 12, 'designation_authority_source': None}
            cp = root / 'context.json'
            hp = root / 'history.jsonl'
            cp.write_text(json.dumps(context))
            rows = []
            for i in range(600):
                x = 0 if 120 <= i < 480 else (-10 if i < 120 else 30)
                v = [0, 0, 0] if 120 <= i < 480 else [2, 0, 0]
                rows.append({'video_frame': i, 'native_frame': i + 100, 'time_s': i / 20, 'subject_id': 7, 'blueprint_id': 'vehicle.mitsubishi.fusorosa', 'position_xyz_m': [x, -5.25, 0], 'velocity_xyz_mps': v})
            hp.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            unknown = measure(hp, cp)
            self.assertEqual(unknown['longest_complete_interval_s'], 18)
            self.assertIsNone(unknown['dwell_exceeds_verified_period'])
            context.update(designation_verified=True, designation_authority_source='synthetic_native_sample/authority-fixture', designated_period_s=12)
            cp.write_text(json.dumps(context))
            self.assertTrue(measure(hp, cp)['dwell_exceeds_verified_period'])
            context['designated_period_s'] = 20
            cp.write_text(json.dumps(context))
            self.assertFalse(measure(hp, cp)['dwell_exceeds_verified_period'])
            rows[230].pop('velocity_xyz_mps')
            hp.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'velocity missing'):
                measure(hp, cp)
