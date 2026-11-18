"""CPU checks for exact runner binding and same-tick yellow/red source rows."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from runner import validate_config
from signal_control import NativeSignalCapture
from yellow_red_capture import YellowRedCapture


class NativeDraftTests(unittest.TestCase):
    def test_config_binds_exact_site_and_case(self):
        config = json.loads((HERE / 'config.json').read_text())
        self.assertIs(validate_config(config), config)
        for key, changed in (('selected_case_id', 'wrong'), ('law_id', 'NRS-484B-257-1')):
            bad = copy.deepcopy(config)
            bad[key] = changed
            with self.assertRaises(ValueError):
                validate_config(bad)
        bad = copy.deepcopy(config)
        bad['site']['xodr_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'site hash differs'):
            validate_config(bad)

    def test_original_yellow_red_row_uses_same_tick_identity(self):
        row = {'frame': 123, 'time_s': 6.15, 'native_signal_id': 17,
               'ego_road_id': 158190, 'ego_lane_id': -1,
               'signal_state': 'Yellow', 'ego_body_vertices_xy_m':
               [[-12, -1], [-12, 1], [-10, 1], [-10, -1]],
               'ego_speed_mps': 2.5}
        video = {'video_frame': 0, 'carla_frame': 123, 'time_s': 6.15}
        with tempfile.TemporaryDirectory() as temp:
            capture = object.__new__(YellowRedCapture)
            capture.history_path = Path(temp) / 'signal_vehicle_history.jsonl'
            capture.yellow_red_count = 0
            with patch.object(NativeSignalCapture, 'capture_tick', return_value=(row, video)):
                observed, frame = capture.capture_tick()
            self.assertEqual(frame, video)
            expected = {
                'frame': 123, 'time_s': 6.15, 'native_signal_id': 17,
                'road_id': 158190, 'lane_id': -1, 'signal_state': 'Yellow',
                'ego_body_vertices_xy_m': row['ego_body_vertices_xy_m'],
                'ego_speed_mps': 2.5}
            self.assertEqual(observed, expected)
            self.assertEqual(json.loads(capture.history_path.read_text()), expected)
            bad = dict(video, video_frame=4)
            with patch.object(NativeSignalCapture, 'capture_tick', return_value=(row, bad)):
                with self.assertRaisesRegex(ValueError, 'frame join differs'):
                    capture.capture_tick()


if __name__ == '__main__':
    unittest.main()
