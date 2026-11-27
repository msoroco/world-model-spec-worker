import json
import os
from pathlib import Path
import tempfile
import unittest

from finalize import finalize
from comparison_audit import audit


class SavedBridgeMeasurement(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, suffix):
        attempt = self.root / suffix
        attempt.mkdir()
        config = {'case_id': 'training__C31675__NRS-484B-450-1m__motor_vehicle_driver__' + suffix,
                  'requested_stationary_footprint_on_bridge': suffix == 'true',
                  'law_id': 'NRS-484B-450-1m', 'cell_id': 'C31675',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20,
                  'duration_s': 30, 'required_atoms': [], 'source_packets': [],
                  'requested_halt_cause': 'voluntary_destination',
                  'cameras': ['overview', 'approach', 'reference_corner', 'driver_reference'],
                  'recording_description': {'channels': []}}
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        (attempt / 'bridge-map.json').write_text(json.dumps({
            'source_kind': 'native_bridge_lane_survey', 'structure_type': 'bridge',
            'deck_polygon_xy_m': [[0, -3.5], [100, -3.5], [100, 0], [0, 0]],
            'native_lane_survey': [{} for _ in range(6)]}) + '\n')
        (attempt / 'road.xodr').write_text('<OpenDRIVE/>\n')
        bridge_rows, map_rows = [], []
        for i in range(600):
            x = (-75 + 50 * min(i / 120, 1)) if suffix == 'false' else (-75 + 125 * min(i / 120, 1))
            speed = 0 if i >= 120 else 8
            bridge_rows.append({'frame': i, 'native_frame': i + 1000, 'time_s': i / 20,
                'speed_mps': speed, 'body_footprint_xy_m': [
                    [x-2, -3], [x+2, -3], [x+2, -1], [x-2, -1]]})
            map_rows.append({'video_frame': i, 'native_frame': i + 1000,
                'time_s': i / 20, 'camera_native_frames': {
                    c: i + 1000 for c in ('overview', 'approach',
                                           'reference_corner', 'driver_reference')}})
        for name, rows in (('bridge-trace.jsonl', bridge_rows),
                           ('video_frames.jsonl', map_rows)):
            (attempt / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            (attempt / (camera + '.mkv')).write_bytes(b'synthetic placeholder, no pixels claimed')
        return attempt

    def test_positive_full_and_ground_control(self):
        for suffix in ('false', 'true'):
            attempt = self.make(suffix)
            report = finalize(attempt, self.root / (suffix + '-report.json'))
            self.assertTrue(report['requested_target_matched'])
            self.assertFalse(report['physical_acceptance_claimed'])
            self.assertIsNone(report['legal_result'])

    def test_missing_source_and_time_join_rejected(self):
        attempt = self.make('true')
        (attempt / 'bridge-map.json').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing required source'):
            finalize(attempt, self.root / 'missing.json')
        attempt = self.make('false')
        path = attempt / 'video_frames.jsonl'
        rows = path.read_text().splitlines()
        first = json.loads(rows[0])
        first['native_frame'] += 1
        rows[0] = json.dumps(first)
        path.write_text('\n'.join(rows) + '\n')
        with self.assertRaisesRegex(ValueError, 'frame join differs'):
            finalize(attempt, self.root / 'bad-join.json')

    def test_independent_comparison_and_fixed_condition_rejection(self):
        ground, bridge = self.make('false'), self.make('true')
        result = audit(ground, bridge)
        self.assertTrue(result['passed'])
        self.assertEqual(result['observed'], {'ground': ['none'], 'bridge': ['full']})
        path = bridge / 'config.json'
        config = json.loads(path.read_text())
        config['duration_s'] = 25
        path.write_text(json.dumps(config) + '\n')
        with self.assertRaisesRegex(ValueError, 'fixed condition changed'):
            audit(ground, bridge)
