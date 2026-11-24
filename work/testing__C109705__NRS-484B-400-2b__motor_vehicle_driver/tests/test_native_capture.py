import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_construction import survey

spec = importlib.util.spec_from_file_location('departure_native_capture', Path(__file__).resolve().parents[1] / 'native_capture.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)

CASE = 'testing__C109705__NRS-484B-400-2b__motor_vehicle_driver__near_centerline'


class Adapter:
    def __init__(self, *, missing_camera=False, missing_entry=False,
                 early_turn=False, resumed_turn=False, stop_at=901):
        self.frame = 0
        self.missing_camera = missing_camera
        self.missing_entry = missing_entry
        self.early_turn = early_turn
        self.resumed_turn = resumed_turn
        self.stop_at = stop_at
        self.stopped = False
        self.destroyed = False
        self.controls = []

    def spawn_ego(self, blueprint, map_name, case_id):
        assert blueprint == 'vehicle.test' and case_id == CASE
        return object()

    def configure_cameras(self, ego, channels, fps):
        assert channels == native.CAMERAS and fps == 20

    def resolve_waypoint(self, waypoint_id):
        return [waypoint_id / 10, 0]

    def apply_control(self, ego, command):
        self.controls.append(command)

    def tick(self):
        self.frame += 1
        return self.frame if self.frame < self.stop_at else self.frame + 1

    def ego_snapshot(self, ego, frame):
        x = frame / 10
        phase = ('approach' if frame < 100 else
                 ('turning' if self.missing_entry else 'intersection_entry') if frame == 100 else
                 'turning' if frame < 400 else 'departure')
        if self.early_turn and frame == 99:
            phase = 'turning'
        if self.resumed_turn and frame == 401:
            phase = 'turning'
        return {'case_id': CASE, 'frame': frame, 'phase': phase,
                'elapsed_seconds': 10 + frame / 20,
                'road_id': 4 if frame >= 400 else 1,
                'driver_control': True, 'position_xy_m': [x, 0],
                'body_corners_xy_m': [[x - 1, -1], [x + 1, -1], [x - 1, 1], [x + 1, 1]],
                'heading_rad': 0, 'speed_mps': 2}

    def camera_frame(self, channel, frame):
        if self.missing_camera and channel == 'right' and frame == 401:
            return None
        return {'channel': channel, 'frame': frame, 'source_path': f'original/{channel}/{frame}.png',
                'source_sha256': 'a' * 64}

    def emergency_stop(self, ego):
        self.stopped = True

    def destroy(self, ego):
        self.destroyed = True


class NativeCaptureTests(unittest.TestCase):
    def _run(self, adapter):
        with tempfile.TemporaryDirectory() as d:
            directory = Path(d)
            source = directory / 'original-map.xodr'
            source.write_text('<OpenDRIVE/>\n')
            s = survey()
            s['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            result = native.capture(adapter, CASE, s, source, directory / 'output')
            trace = json.loads(Path(result['trace_path']).read_text())
            index = json.loads(Path(result['camera_index_path']).read_text())
            return result, trace, index

    def test_original_trace_and_four_camera_index(self):
        adapter = Adapter()
        result, trace, index = self._run(adapter)
        self.assertEqual(result['frames'], 900)
        self.assertFalse(result['physical_acceptance_claimed'])
        self.assertEqual(len(trace['samples']), 900)
        self.assertEqual({key: len(value) for key, value in index['channels'].items()},
                         dict.fromkeys(native.CAMERAS, 900))
        self.assertTrue(adapter.stopped and adapter.destroyed)
        self.assertEqual(len(adapter.controls), 900)

    def test_missing_original_camera_rejected_and_ego_cleaned(self):
        adapter = Adapter(missing_camera=True)
        with self.assertRaisesRegex(ValueError, 'four-camera'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_missing_entry_rejected_and_ego_cleaned(self):
        adapter = Adapter(missing_entry=True)
        with self.assertRaisesRegex(ValueError, 'before observed intersection entry'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_turn_before_entry_rejected_and_ego_cleaned(self):
        adapter = Adapter(early_turn=True)
        with self.assertRaisesRegex(ValueError, 'before observed intersection entry'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_return_to_turning_after_departure_rejected(self):
        adapter = Adapter(resumed_turn=True)
        with self.assertRaisesRegex(ValueError, 'regressed after departure'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_frame_gap_rejected_and_ego_cleaned(self):
        adapter = Adapter(stop_at=10)
        with self.assertRaisesRegex(ValueError, 'frame'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_native_clock_drift_rejected_and_ego_cleaned(self):
        adapter = Adapter()
        original = adapter.ego_snapshot
        def drift(ego, frame):
            row = original(ego, frame)
            if frame == 75:
                row['elapsed_seconds'] += 0.02
            return row
        adapter.ego_snapshot = drift
        with self.assertRaisesRegex(ValueError, '20 Hz clock drift'):
            self._run(adapter)
        self.assertTrue(adapter.stopped and adapter.destroyed)

    def test_existing_original_capture_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'original-map.xodr'
            source.write_text('<OpenDRIVE/>\n')
            selected = survey()
            selected['source_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
            output = root / 'output'
            output.mkdir()
            original = output / 'original-trace.json'
            original.write_text('retained original\n')
            adapter = Adapter()
            with self.assertRaisesRegex(ValueError, 'overwrite original Native capture'):
                native.capture(adapter, CASE, selected, source, output)
            self.assertEqual(original.read_text(), 'retained original\n')
            self.assertEqual(adapter.controls, [])


if __name__ == '__main__':
    unittest.main()
