import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_capture as capture_module
from yield_view_measurement import ASSIGNMENT


class Pipe:
    def __init__(self):
        self.closed = False
        self.count = 0

    def write(self, data):
        self.count += len(data)

    def close(self):
        self.closed = True


class Process:
    def __init__(self, target):
        target.write_bytes(b'synthetic video bytes')
        self.stdin = Pipe()
        self.stderr = SimpleNamespace(read=lambda: b'')

    def wait(self, timeout=None):
        return 0

    def poll(self):
        return 0


class World:
    def __init__(self):
        self.settings = SimpleNamespace(synchronous_mode=False, fixed_delta_seconds=None)
        self.frame = 99

    def get_settings(self):
        return self.settings

    def apply_settings(self, value):
        self.settings = value

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return SimpleNamespace(frame=self.frame,
                               timestamp=SimpleNamespace(elapsed_seconds=10+(self.frame-100)/20))


class Adapter:
    def __init__(self, site, case_id):
        self.site = site
        self.case_id = case_id

    def read_original_context(self, site, case_id):
        return {'assignment_id': ASSIGNMENT, 'case_id': case_id,
                'source_kind': 'original_native_readback',
                'source_recording_id': 'original-fixture',
                'intersection_id': site['intersection_id'],
                'control': 'yield_sign', 'stop_line_present': False,
                'near_crosswalk_present': False,
                'sidewalk_derived_crosswalk_present': False,
                'police_control_active': False,
                'traffic_signal_control_active': False,
                'approach_view_stations': [{'station_id': 'v',
                                            'distance_to_intersection_m': 1,
                                            'view_of_through_traffic': True}],
                **{key: site[key] for key in capture_module.SOURCE_FIELDS}}

    def control_frame(self, case_id, index):
        pass

    def read_original_frame(self, case_id, index, frame):
        return {'case_id': case_id, 'frame': index, 'native_frame': frame,
                'original_frame': frame, 'time_s': index/20,
                'actor_id': 1, 'vehicle_blueprint': 'vehicle.fixture',
                'position_m': [float(index), 0., 0.], 'heading_xy': [1., 0.],
                'body_vertices_m': [[0., 0., 0.], [1., 0., 0.],
                                    [1., 1., 0.], [0., 1., 0.]],
                'ego_speed_mps': 1., 'ego_within_intersection': index == 1,
                'distance_to_intersection_m': float(2-index),
                'through_vehicle_ids': ['t'],
                'through_vehicles': [{'id': 't', 'through_highway': True,
                                      'distance_to_conflict_m': 2., 'speed_mps': 1.}],
                'control': 'yield_sign', 'stop_line_present': False,
                'near_crosswalk_present': False,
                **{key: self.site[key] for key in capture_module.SOURCE_FIELDS}}

    def camera_rgb24(self, view, native_frame):
        return bytes(12)


class NativeCaptureTests(unittest.TestCase):
    def test_source_sealed_capture_restores_world(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as tmp:
            root = Path(tmp)
            site = {'source_records': {}, 'intersection_id': 'intersection-fixture'}
            for key in capture_module.SOURCE_FIELDS:
                source = root / (key+'.source')
                source.write_text(key+' original fixture\n')
                digest = hashlib.sha256(source.read_bytes()).hexdigest()
                site[key] = digest
                site['source_records'][key] = {'path': source.name, 'sha256': digest}
            site_path = root / 'site.json'
            site_path.write_text(json.dumps(site)+'\n')
            site['_source_path'] = str(site_path)
            site['_source_sha256'] = hashlib.sha256(site_path.read_bytes()).hexdigest()
            world = World()
            adapter = Adapter(site, ASSIGNMENT+'__yield_slow_hazard')
            attempt = root / 'attempt'
            attempt.mkdir()
            (attempt / 'config.json').write_text('{"materialized": true}\n')
            def encoder(output, view):
                return Process(output/(view+'.mkv'))
            with patch.object(capture_module, 'FRAMES', 3), \
                    patch.object(capture_module, 'SIZES', {v:(2,2) for v in capture_module.VIEWS}), \
                    patch.object(capture_module, '_encoder', side_effect=encoder):
                result = capture_module.capture(world, adapter, site, adapter.case_id,
                                                attempt, site['_source_sha256'])
            self.assertTrue(Path(result['receipt']).is_file())
            self.assertTrue((attempt / 'config.json').is_file())
            self.assertTrue((attempt / 'reviewed-sources.json').is_file())
            self.assertFalse(world.get_settings().synchronous_mode)
            self.assertIsNone(world.get_settings().fixed_delta_seconds)
            receipt = json.loads(Path(result['receipt']).read_text())
            self.assertEqual(receipt['trace_sha256'],
                             hashlib.sha256(Path(result['trace']).read_bytes()).hexdigest())

    def test_missing_reviewed_site_hash_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']) as tmp:
            with self.assertRaisesRegex(ValueError, 'reviewed yield site source changed'):
                capture_module.capture(World(), Adapter({}, ASSIGNMENT+'__yield_slow_hazard'),
                                       {}, ASSIGNMENT+'__yield_slow_hazard', Path(tmp)/'bad', 'b'*64)

    def test_crossing_without_through_vehicle_rejected_at_capture(self):
        case_id = ASSIGNMENT+'__yield_slow_hazard'
        site = {key: 'a'*64 for key in capture_module.SOURCE_FIELDS}
        row = Adapter(site, case_id).read_original_frame(case_id, 1, 101)
        row['through_vehicles'] = []
        row['through_vehicle_ids'] = []
        with self.assertRaisesRegex(ValueError, 'through-vehicle crossing'):
            capture_module._validate_row(row, 1, 101, site, case_id)


if __name__ == '__main__':
    unittest.main()
