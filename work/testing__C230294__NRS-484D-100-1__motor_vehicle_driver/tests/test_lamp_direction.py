import importlib.util
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


path = Path(__file__).resolve().parents[1] / 'lamp_direction.py'
spec = importlib.util.spec_from_file_location('lamp_direction', path)
probe = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = probe
spec.loader.exec_module(probe)
import importlib
sys.path.insert(0, str(path.parent))
source_packet = importlib.import_module('source_packet')
runner = importlib.import_module('runner')
native_acquisition = importlib.import_module('native_acquisition')
saved_audit = importlib.import_module('saved_audit')
finalize_original = importlib.import_module('finalize_original')
native_publication = importlib.import_module('native_publication')


def scene(case):
    s = dict(cell_id='C230294', actor='motor_vehicle_driver',
             nevada_jurisdiction=True, public_highway=True,
             vehicle_class='ordinary_motor_vehicle', parked=False,
             map_sha256='reviewed_map_sha256',
             device_directs=case.device_directs,
             lamps_on_request=case.lamps_on, context=case.context,
             official_device=case.device_directs,
             device_message='use_lamps' if case.device_directs else 'no_device',
             device_operative=case.device_directs,
             device_governs_route=case.device_directs,
             required_lamp_ids=['headlamp_left', 'headlamp_right'],
             required_lamp_provisions={'headlamp_left': 'NRS 484D class-specific provision',
                                       'headlamp_right': 'NRS 484D class-specific provision'},
             highway={'public_dedication': True, 'boundaries_documented': True,
                      'public_vehicular_access': True},
             device_authority={'public_authority_placed': True,
                               'nrs_484a_145_qualified': True,
                               'agency': 'reviewed agency', 'review_reference': 'site source'},
             device_timing={'operative': True, 'start_time_s': 1,
                            'end_time_s': 86399},
             route_xy=[[0, 0], [20, 0]], device_xy=[5, 2],
             sunset_time_s=60000, sunrise_time_s=20000,
             clock_time_s=62000 if case.context == 'night' else 30000,
             visibility_ahead_m=250 if case.context == 'poor_visibility' else 400)
    for field in ('jurisdiction', 'highway', 'vehicle_class', 'parking_status',
                  'required_lamp_provisions', 'device_authority',
                  'device_geometry', 'device_message', 'device_timing',
                  'route', 'sunset_sunrise', 'clock', 'visibility'):
        s[field + '_source_sha256'] = 'a' * 64
    return s


def rows(case, s):
    output = []
    for i in range(900):
        row = dict(original_frame=100+i, time_s=i/20,
                   vehicle_id='ego', speed_mps=5,
                   device_directs=case.device_directs, context=case.context,
                   lamp_states={x: case.lamps_on for x in s['required_lamp_ids']},
                   vehicle_class_source_sha256=s['vehicle_class_source_sha256'])
        for field in ('frame', 'vehicle_motion', 'lamp_state',
                      'device_authority', 'device_message', 'device_timing',
                      'sunset_sunrise', 'clock', 'visibility'):
            row[field + '_source_sha256'] = 'a' * 64
        output.append(row)
    return output


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def __getattr__(self, name):
        def invoke(*args):
            self.calls.append((name, args))
            if name == 'spawn_vehicle':
                return None if self.fail else 'ego'
            if name == 'place_official_device':
                return 'device'
        return invoke


class LampTests(unittest.TestCase):
    def test_exact_time_and_visibility_boundaries_are_separate(self):
        s = scene(probe.CASES[0])
        s['clock_time_s'] = 61799
        s['visibility_ahead_m'] = 304.8
        self.assertFalse(probe.statutory_context(s)['half_hour_night'])
        self.assertFalse(probe.statutory_context(s)['under_1000ft_discernibility'])
        s['clock_time_s'] = 61800
        s['visibility_ahead_m'] = 304.799
        self.assertTrue(probe.statutory_context(s)['half_hour_night'])
        self.assertTrue(probe.statutory_context(s)['under_1000ft_discernibility'])
        s['clock_time_s'] = 18200
        self.assertTrue(probe.statutory_context(s)['half_hour_night'])
        s['clock_time_s'] = 18201
        self.assertFalse(probe.statutory_context(s)['half_hour_night'])

    def write_packet(self, root, case):
        s = scene(case)
        sources = {}
        for field in source_packet.SOURCE_FIELDS:
            s.setdefault(field, field + '_reviewed_value')
            raw = (json.dumps({field: s[field]}) + '\n').encode()
            name = field + '.json'
            (root / name).write_bytes(raw)
            checksum = hashlib.sha256(raw).hexdigest()
            s[field + '_source_sha256'] = checksum
            sources[field] = {'path': name, 'sha256': checksum}
        raw = (json.dumps({'device_message': s['device_message']}) + '\n').encode()
        (root / 'device_message.json').write_bytes(raw)
        sources['device_message']['sha256'] = hashlib.sha256(raw).hexdigest()
        s['device_message_source_sha256'] = sources['device_message']['sha256']
        packet = root / 'packet.json'
        packet.write_text(json.dumps({'case_id': source_packet.ASSIGNMENT + '__' + case.name,
                                      'scene': s, 'sources': sources}) + '\n')
        return packet, s

    def test_all_cases_construct_and_measure(self):
        for case in probe.CASES:
            with self.subTest(case=case.name):
                s = scene(case)
                adapter = Adapter()
                probe.construct(adapter, s, case)
                self.assertEqual([x[0] for x in adapter.calls].count('set_lamp'), 2)
                measured = probe.measure_original(rows(case, s), s, case)
                self.assertEqual(measured['lamp_on_frame_counts']['headlamp_left'],
                                 900 if case.lamps_on else 0)
                self.assertIsNone(measured['legal_judgment'])

    def test_missing_source_and_lamp_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        records = rows(case, s)
        del records[2]['device_timing_source_sha256']
        with self.assertRaisesRegex(ValueError, 'source missing'):
            probe.measure_original(records, s, case)
        records = rows(case, s)
        del records[2]['lamp_states']['headlamp_right']
        with self.assertRaisesRegex(ValueError, 'lamp states missing'):
            probe.measure_original(records, s, case)

    def test_unofficial_device_and_spawn_rejected(self):
        case = probe.CASES[0]
        s = scene(case)
        s['official_device'] = False
        with self.assertRaisesRegex(ValueError, 'official lamp direction'):
            probe.validate_scene(s, case)
        s = scene(case)
        s['device_authority']['nrs_484a_145_qualified'] = False
        with self.assertRaisesRegex(ValueError, 'authority source incomplete'):
            probe.validate_scene(s, case)
        s = scene(case)
        s['required_lamp_provisions'].pop('headlamp_right')
        with self.assertRaisesRegex(ValueError, 'provision citations missing'):
            probe.validate_scene(s, case)
        with self.assertRaisesRegex(ValueError, 'vehicle spawn failed'):
            probe.construct(Adapter(fail=True), scene(case), case)
        neutral = scene(probe.CASES[2])
        neutral['device_message'] = 'use_lamps'
        with self.assertRaisesRegex(ValueError, 'no-device comparison control changed'):
            probe.validate_scene(neutral, probe.CASES[2])

    def test_source_packet_binds_actual_bytes_and_assertions(self):
        case = probe.CASES[0]
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            packet, s = self.write_packet(root, case)
            verified = source_packet.verify(packet, case.name)
            self.assertEqual(verified['case'].name, case.name)
            (root / 'device_message.json').write_text('{"device_message":"different"}\n')
            with self.assertRaisesRegex(ValueError, 'bytes changed'):
                source_packet.verify(packet, case.name)

    def test_runner_static_and_comparison_isolation(self):
        checked = runner.check()
        self.assertEqual(checked['rate_hz'], 20)
        base = dict(case_id=probe.CASES[0].name, frame_count=900,
                    lamp_on_frame_counts={'headlamp_left': 900}, map_sha256='map',
                    vehicle_class_source_sha256='class', route_source_sha256='route',
                    required_lamp_provisions_source_sha256='provisions',
                    camera_profile_sha256='cameras')
        other = dict(base, case_id=probe.CASES[1].name,
                     lamp_on_frame_counts={'headlamp_left': 0})
        probe.audit_comparison([base, other], probe.CASES[:2], {'lamps_on'})
        other['map_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'fixed context changed'):
            probe.audit_comparison([base, other], probe.CASES[:2], {'lamps_on'})

    def test_saved_original_capture_and_missing_camera_rejection(self):
        case = probe.CASES[0]
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            packet, s = self.write_packet(root, case)
            original_rows = rows(case, s)

            class Pipeline:
                def __init__(self):
                    self.frames = []
                def capture(self, frame, time_s):
                    self.frames.append(frame)
                def close(self):
                    pass

            class Native(Adapter):
                def __init__(self):
                    super().__init__()
                    self.pipeline = Pipeline()
                    self.destroyed = []
                    self.restored = False
                def loaded_map_sha256(self):
                    return s['map_sha256']
                def snapshot_settings(self):
                    return 'saved'
                def configure_sync(self, rate_hz):
                    self.rate_hz = rate_hz
                def readback_sync(self, rate_hz):
                    return self.rate_hz == rate_hz
                def spawn_cameras(self, vehicle, names, scene):
                    return {name: 'camera-' + name for name in names}
                def start_pipeline_capture(self, vehicle, output, case_id):
                    return self.pipeline
                def tick_capture(self, index, scene, cameras):
                    row = original_rows[index]
                    return row, {name: {'original_frame': row['original_frame'],
                                        'sensor_id': actor, 'bytes': b'fixture-image'}
                                 for name, actor in cameras.items()}
                def actor_id(self, actor):
                    return actor
                def destroy(self, actor):
                    self.destroyed.append(actor)
                def restore_settings(self, settings):
                    self.restored = settings == 'saved'
                def readback_restored(self, settings):
                    return self.restored

            adapter = Native()
            attempt = root / 'attempt'
            measured = native_acquisition.acquire(adapter, packet, attempt)
            self.assertEqual(measured['lamp_on_frame_counts']['headlamp_left'], 900)
            self.assertEqual(len(adapter.pipeline.frames), 900)
            self.assertTrue(adapter.restored)
            self.assertEqual(len(adapter.destroyed), 6)
            checked = saved_audit.audit_saved(attempt, case.name)
            self.assertEqual(checked['camera_count'], 4)
            report = finalize_original.finalize(attempt, case.name)
            self.assertEqual(report['measurements']['required_lamp_states']['value']['on_frame_counts']['headlamp_left'], 900)
            self.assertIsNone(report['legal_verdict'])
            fixture_config = json.loads((path.parent / 'config.json').read_text())
            fixture_config['selected_case_id'] = source_packet.ASSIGNMENT + '__' + case.name
            fixture_config['case']['lamps_on'] = case.lamps_on
            (attempt / 'config.json').write_text(json.dumps(fixture_config) + '\n')
            (attempt / 'construction.json').write_text((path.parent / 'construction.json').read_text())
            (attempt / 'trace.jsonl').write_text(''.join(json.dumps({
                'frame': row['original_frame'], 'time_s': row['time_s'],
                'position': {'x': i / 4, 'y': 0, 'z': 0},
                'heading_deg': 0, 'speed_mps': row['speed_mps']}) + '\n'
                for i, row in enumerate(original_rows)))
            (attempt / 'video_frames.jsonl').write_text(''.join(json.dumps({
                'video_frame': i, 'carla_frame': row['original_frame'],
                'time_s': row['time_s']}) + '\n'
                for i, row in enumerate(original_rows)))
            for view in native_publication.VIDEOS:
                (attempt / view).write_text('diagnostic placeholder for publication unit test\n')
            published = native_publication.publish(attempt, report)
            self.assertEqual(published['measured_values']['frame_count'], 900)
            self.assertEqual(len(published['recording_evidence']), 23)
            self.assertFalse(published['setup_confirmed'])
            (attempt / 'cameras/overview/0001.png').unlink()
            with self.assertRaisesRegex(ValueError, 'camera source missing'):
                saved_audit.audit_saved(attempt, case.name)
            with self.assertRaisesRegex(ValueError, 'camera source missing'):
                finalize_original.finalize(attempt, case.name)


if __name__ == '__main__':
    unittest.main()
