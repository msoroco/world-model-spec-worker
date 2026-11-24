"""Full-window source-shaped positive and fail-closed telemetry tests."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure import SOURCES, measure, sha


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rows(path, value):
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in value))


def sample(folder, *, engine=False, brake=True, wheel=-20):
    folder.mkdir()
    write(folder / 'grade-readback.json', {
        'format': 'c276263-grade-readback-v1', 'source_kind': 'synthetic_cpu',
        'road_id': 1, 'slope_fraction': .04, 'right_curb_y_m': -3.5})
    vehicle, occupancy, video = [], [], []
    for i in range(600):
        common = {'frame': i, 'native_frame': i + 900, 'time_s': i / 20}
        vehicle.append(dict(common, source_kind='synthetic_native_sample', actor_id=8,
            engine_source='synthetic_instrument', wheel_source='synthetic_instrument',
            brake_source='synthetic_instrument', engine_running=engine,
            parking_brake_set=brake, front_wheel_heading_to_curb_deg=wheel,
            speed_mps=0, position_x_m=0))
        occupancy.append(dict(common, source_kind='synthetic_cpu',
            occupant_count=1 if i < 100 else 0,
            responsible_person_outside=i >= 100))
        video.append({'video_frame': i, 'native_frame': i + 900,
                      'carla_frame': i + 900, 'time_s': i / 20,
                      'camera_raw_sha256': {view: hashlib.sha256(
                          f'{view}:{i}'.encode()).hexdigest()
                          for view in ('overview', 'curb', 'wheel', 'cabin')}})
    rows(folder / SOURCES[0], vehicle)
    rows(folder / SOURCES[2], occupancy)
    rows(folder / SOURCES[3], video)


def hashes(folder):
    return {name: sha(folder / name) for name in SOURCES}


class SavedThreeDutyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve())
        self.folder = Path(self.temp.name) / 'reference'
        sample(self.folder)
    def tearDown(self):
        self.temp.cleanup()
    def test_full_window(self):
        result = measure(self.folder, hashes(self.folder), diagnostic=True)
        self.assertEqual(len(result['unattended_frames']), 500)
        self.assertFalse(result['engine_running_any'])
        self.assertFalse(result['parking_brake_unset_any'])
        self.assertIsNone(result['legal_verdict'])
    def test_original_provenance_rejects_synthetic(self):
        with self.assertRaisesRegex(ValueError, 'source differs'):
            measure(self.folder, hashes(self.folder))
    def test_missing_engine_sensor(self):
        path = self.folder / SOURCES[0]
        rows_in = [json.loads(s) for s in path.read_text().splitlines()]
        rows_in[100]['engine_source'] = 'unknown'
        rows(path, rows_in)
        with self.assertRaisesRegex(ValueError, 'engine state absent'):
            measure(self.folder, hashes(self.folder), diagnostic=True)
    def test_missing_wheel_sensor(self):
        path = self.folder / SOURCES[0]
        rows_in = [json.loads(s) for s in path.read_text().splitlines()]
        rows_in[100]['wheel_source'] = 'unknown'
        rows(path, rows_in)
        with self.assertRaisesRegex(ValueError, 'front-wheel state absent'):
            measure(self.folder, hashes(self.folder), diagnostic=True)
    def test_frame_mismatch(self):
        path = self.folder / SOURCES[3]
        rows_in = [json.loads(s) for s in path.read_text().splitlines()]
        rows_in[100]['native_frame'] += 1
        rows(path, rows_in)
        with self.assertRaisesRegex(ValueError, 'frame/time join differs'):
            measure(self.folder, hashes(self.folder), diagnostic=True)
    def test_changed_hash(self):
        altered = hashes(self.folder)
        altered[SOURCES[0]] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'hash differs'):
            measure(self.folder, altered, diagnostic=True)


if __name__ == '__main__':
    unittest.main()

class NativeCaptureBoundaryTest(unittest.TestCase):
    def test_native_capture_contract(self):
        from capture import check
        row = check()
        self.assertEqual(row['frames'], 600)
        self.assertEqual(len(row['cameras']), 4)
        self.assertEqual(row['cases']['reference'], {'brake': True, 'steer': -.55})
        self.assertEqual(row['cases']['contrast'], {'brake': False, 'steer': 0.0})
        self.assertEqual(row['engine_wheel_occupancy_instrumentation'],
                         'unavailable_in_native_api')

    def test_native_map_survey(self):
        from capture import _survey
        from grade import open_drive
        class Location:
            def __init__(self, x, y, z):
                self.x, self.y, self.z = x, y, z
        class Carla:
            class LaneType:
                Driving = 'driving'
        Carla.Location = Location
        class Map:
            def to_opendrive(self):
                return open_drive()
            def get_waypoint(self, location, project_to_road, lane_type):
                self_location = type('P', (), {'x': 0, 'y': -1.75, 'z': 4})()
                return type('W', (), {'road_id': 1, 'lane_id': -1,
                    'transform': type('T', (), {'location': self_location})()})()
        row = _survey(Map(), Carla)
        self.assertEqual(row['slope_fraction'], .04)
        self.assertEqual(row['right_curb_y_m'], -3.5)

    def test_native_shape_missing_attendance_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            folder = Path(tmp) / 'native_shape'
            sample(folder)
            path = folder / SOURCES[1]
            grade = json.loads(path.read_text())
            grade['source_kind'] = 'native_map'
            write(path, grade)
            path = folder / SOURCES[0]
            vehicle = [json.loads(s) for s in path.read_text().splitlines()]
            for row in vehicle:
                row.update(source_kind='native_actor', engine_source='instrumented_engine_sensor_missing',
                           engine_running=None, brake_source='native_control_readback',
                           wheel_source='instrumented_front_wheel_sensor_missing',
                           front_wheel_heading_to_curb_deg=None)
            rows(path, vehicle)
            path = folder / SOURCES[2]
            attendance = [json.loads(s) for s in path.read_text().splitlines()]
            for row in attendance:
                row.update(source_kind='occupancy_sensor_missing', occupant_count=None,
                           responsible_person_outside=None)
            rows(path, attendance)
            with self.assertRaisesRegex(ValueError, 'Occupancy provenance differs'):
                measure(folder, hashes(folder))
