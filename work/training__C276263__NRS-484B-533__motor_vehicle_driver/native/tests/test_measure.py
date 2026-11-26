"""Full-window source-shaped positive and fail-closed telemetry tests."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure import SOURCES, measure, sha
from instrumentation import InstrumentClient, validate_packet, wheel_angles
from comparison import compare, isolated_duty_contrast


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rows(path, value):
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in value))


def sample(folder, *, engine=False, brake=True, wheel=-20):
    folder.mkdir()
    write(folder / 'grade-readback.json', {
        'format': 'c276263-grade-readback-v1', 'source_kind': 'synthetic_cpu',
        'road_id': 1, 'slope_fraction': .04, 'right_curb_y_m': -3.5})
    vehicle, occupancy, video, trace, instrument = [], [], [], [], []
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
                          for view in ('overview', 'approach', 'reference_corner',
                                       'driver_reference')}})
        trace.append({'frame': i + 900, 'time_s': i / 20,
                      'position': {'x': 0, 'y': -1.75, 'z': 4},
                      'heading_deg': 0, 'speed_mps': 0})
        instrument.append({'native_frame': i + 900, 'actor_id': 8,
                           'source_kind': 'synthetic_cpu',
                           'engine_running': engine,
                           'front_wheel_heading_to_curb_deg': wheel,
                           'occupant_count': 1 if i < 100 else 0,
                           'responsible_person_outside': i >= 100})
    rows(folder / SOURCES[0], vehicle)
    rows(folder / SOURCES[2], occupancy)
    rows(folder / SOURCES[3], video)
    rows(folder / SOURCES[4], trace)
    rows(folder / SOURCES[5], instrument)


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
    def test_trace_position_mismatch(self):
        path = self.folder / SOURCES[4]
        rows_in = [json.loads(s) for s in path.read_text().splitlines()]
        rows_in[100]['position']['x'] = 5
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
        self.assertEqual(row['camera_dimensions']['overview'], [1920, 1080])
        self.assertEqual(row['cameras'], ['overview', 'approach',
                                          'reference_corner', 'driver_reference'])
        self.assertEqual(row['cases']['reference'], {'brake': True, 'steer': -.55})
        self.assertEqual(row['cases']['contrast'], {'brake': False, 'steer': 0.0})
        self.assertEqual(row['engine_wheel_occupancy_instrumentation'],
                         'external_original_service_required')

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


class OriginalInstrumentBoundaryTest(unittest.TestCase):
    def packet(self):
        return {'format': 'c276263-original-instrument-v1',
                'native_frame': 901, 'actor_id': 8,
                'source_kind': 'original_instrumentation',
                'instrument_id': 'instrument-rig-1',
                'engine_method': 'engine-rpm-sensor',
                'wheel_calibration_id': 'curb-relative-wheel-calibration-1',
                'attendance_method': 'identified-person-and-cabin-inventory',
                'responsible_person_id': 'person-1',
                'engine_running': False, 'occupant_count': 0,
                'responsible_person_outside': True,
                'front_wheel_heading_to_curb_deg': -22.0}

    def test_packet_joins_and_rejects_proxies(self):
        packet = self.packet()
        self.assertIs(validate_packet(packet, 901, 8), packet)
        for key, value, error in (
                ('native_frame', 902, 'frame or actor'),
                ('engine_method', 'command', 'not original operation'),
                ('attendance_method', 'case_label', 'not original occupancy'),
                ('engine_running', None, 'observation missing'),
                ('front_wheel_heading_to_curb_deg', float('nan'), 'observation missing')):
            changed = dict(packet, **{key: value})
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, error):
                validate_packet(changed, 901, 8)

    def test_native_front_wheels_are_read_separately(self):
        class WheelLocation:
            FL_Wheel = 'fl'
            FR_Wheel = 'fr'
        class Carla:
            VehicleWheelLocation = WheelLocation
        class Vehicle:
            attributes = {'number_of_wheels': '4'}
            def get_wheel_steer_angle(self, wheel):
                return {'fl': -19.0, 'fr': -21.0}[wheel]
        self.assertEqual(wheel_angles(Vehicle(), Carla),
                         {'front_left': -19.0, 'front_right': -21.0})

    def test_client_requests_exact_frame(self):
        client = InstrumentClient.__new__(InstrumentClient)
        client.reader = io.StringIO(json.dumps(self.packet()) + '\n')
        client.writer = io.StringIO()
        packet = client.sample(901, 8, {'front_left': -19.0,
                                        'front_right': -21.0})
        request = json.loads(client.writer.getvalue())
        self.assertEqual(request['native_frame'], packet['native_frame'])
        self.assertEqual(request['actor_id'], packet['actor_id'])
        self.assertEqual(set(request['native_front_wheel_angles_deg']),
                         {'front_left', 'front_right'})

    def test_full_original_shaped_source_join(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            folder = Path(tmp) / 'original_shape'
            sample(folder)
            grade_path = folder / SOURCES[1]
            grade = json.loads(grade_path.read_text())
            grade['source_kind'] = 'native_map'
            write(grade_path, grade)
            vehicle_path = folder / SOURCES[0]
            vehicle = [json.loads(s) for s in vehicle_path.read_text().splitlines()]
            for row in vehicle:
                row.update(source_kind='native_actor', engine_source='instrumented_engine_sensor',
                           brake_source='native_control_readback',
                           wheel_source='instrumented_front_wheel_sensor',
                           instrument_id='rig-1', engine_method='engine-rpm-sensor',
                           wheel_calibration_id='calibration-1',
                           front_wheel_angles_native_deg={'front_left': -19.0,
                                                          'front_right': -21.0})
            rows(vehicle_path, vehicle)
            occupancy_path = folder / SOURCES[2]
            occupancy = [json.loads(s) for s in occupancy_path.read_text().splitlines()]
            for row in occupancy:
                row.update(source_kind='occupancy_sensor', instrument_id='rig-1',
                           responsible_person_id='person-1',
                           attendance_method='identified-person-and-cabin-inventory')
            rows(occupancy_path, occupancy)
            packet_path = folder / SOURCES[5]
            packets = [json.loads(s) for s in packet_path.read_text().splitlines()]
            for packet in packets:
                packet.update(source_kind='original_instrumentation',
                              instrument_id='rig-1', engine_method='engine-rpm-sensor',
                              wheel_calibration_id='calibration-1',
                              attendance_method='identified-person-and-cabin-inventory',
                              responsible_person_id='person-1')
            rows(packet_path, packets)
            measured = measure(folder, hashes(folder))
            self.assertEqual(measured['source_kind'], 'original_native')
            self.assertEqual(len(measured['unattended_frames']), 500)
            vehicle[150]['instrument_id'] = 'another-rig'
            rows(vehicle_path, vehicle)
            with self.assertRaisesRegex(ValueError, 'method or identity differs'):
                measure(folder, hashes(folder))


class SourceBoundComparisonTest(unittest.TestCase):
    def test_each_statutory_duty_has_separate_fixed_condition_cpu_contrast(self):
        choices = {
            'engine_operation': {'engine': True},
            'parking_brake_state': {'brake': False},
            'front_wheel_orientation': {'wheel': 0},
        }
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            reference = Path(tmp) / 'reference'
            sample(reference)
            for duty, changed in choices.items():
                contrast = Path(tmp) / duty
                sample(contrast, **changed)
                receipt = isolated_duty_contrast(
                    reference, contrast, hashes(reference), hashes(contrast),
                    duty, diagnostic=True)
                self.assertTrue(all(receipt['fixed_checks'].values()))
                self.assertFalse(receipt['physical_or_legal_acceptance'])
                for other in choices:
                    if other != duty:
                        with self.assertRaisesRegex(ValueError, 'contrast absent'):
                            isolated_duty_contrast(
                                reference, contrast, hashes(reference),
                                hashes(contrast), other, diagnostic=True)

    def test_declared_difference_and_fixed_conditions(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            reference = Path(tmp) / 'reference'
            contrast = Path(tmp) / 'contrast'
            sample(reference)
            sample(contrast, brake=False, wheel=0)
            result = compare(reference, contrast, hashes(reference), hashes(contrast),
                             diagnostic=True)
            self.assertTrue(all(result['fixed_checks'].values()))
            self.assertTrue(all(result['difference_checks'].values()))
            self.assertFalse(result['isolates_individual_duties'])
            self.assertEqual(set(result['statutory_duty_observations']['reference']),
                             {'engine_operation', 'parking_brake_state',
                              'front_wheel_orientation'})
            self.assertFalse(result['physical_or_legal_acceptance'])
            rows_in = [json.loads(s) for s in (contrast / SOURCES[0]).read_text().splitlines()]
            for row in rows_in:
                row['parking_brake_set'] = True
            rows(contrast / SOURCES[0], rows_in)
            with self.assertRaisesRegex(ValueError, 'contrast absent'):
                compare(reference, contrast, hashes(reference), hashes(contrast),
                        diagnostic=True)

    def test_changed_fixed_grade_rejected(self):
        with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR']).resolve()) as tmp:
            reference = Path(tmp) / 'reference'
            contrast = Path(tmp) / 'contrast'
            sample(reference)
            sample(contrast, brake=False, wheel=0)
            grade_path = contrast / SOURCES[1]
            grade = json.loads(grade_path.read_text())
            grade['slope_fraction'] = .08
            write(grade_path, grade)
            with self.assertRaisesRegex(ValueError, 'Fixed original comparison'):
                compare(reference, contrast, hashes(reference), hashes(contrast),
                        diagnostic=True)
