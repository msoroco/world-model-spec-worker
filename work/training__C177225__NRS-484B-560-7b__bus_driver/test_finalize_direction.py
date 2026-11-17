import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from finalize_direction import process_saved, signal_case_id
from native_scene import VIEWS


ROOT = Path(__file__).resolve().parents[2]


def _write_json(path, value):
    path.write_text(json.dumps(value) + '\n')


class SavedDirectionTest(unittest.TestCase):
    def test_saved_rows_and_four_decoded_sources(self):
        scratch = ROOT / '.runtime-work'
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='c177225-saved-', dir=scratch) as tmp:
            root = Path(tmp)
            _write_json(root / 'config.json', {
                'case_id': signal_case_id('reference'), 'case_suffix': 'reference',
                'direction': 1, 'rate_hz': 20, 'frames': 2})
            _write_json(root / 'officer_signal_definition.json', {
                'officer_id': 'officer-1', 'bus_id': 'bus-1', 'direction': 1,
                'issued_frame': 0, 'first_governing_frame': 1,
                'last_governing_frame': 2, 'crossing_id': 'crossing-1',
                'authorized': True, 'hand_signal': 'STOP'})
            rows = []
            signals = []
            maps = []
            for frame, station in ((1, -20), (2, -13.75)):
                rows.append({'native_frame': frame, 'actor_id': 'bus-1',
                             'station_m': station,
                             'velocity_native_xyz_mps': [0, 0, 0]})
                signals.append({'native_frame': frame, 'actor_id': 'officer-1',
                                'recipient_actor_id': 'bus-1', 'crossing_id': 'crossing-1',
                                'direction': 1, 'authorized': True,
                                'hand_signal': 'STOP', 'governing': True,
                                'pose_control_applied': True,
                                'pose_bone_readback': 'crl_arm__R'})
                maps.append({'native_frame': frame, 'carla_frame': frame,
                             'video_frame': frame - 1, 'time_s': frame / 20})
            for name, values in (('bus_native_rows.jsonl', rows),
                                 ('officer_signal_rows.jsonl', signals),
                                 ('video_frames.jsonl', maps)):
                (root / name).write_text(''.join(json.dumps(row) + '\n' for row in values))
            for name in VIEWS:
                subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                '-f', 'lavfi', '-i', 'color=c=blue:s=1280x720:r=20',
                                '-frames:v', '2', '-c:v', 'ffv1', str(root / (name + '.mkv'))],
                               check=True, timeout=30)
            observed = process_saved(root, source_kind='synthetic_native_sample')
            self.assertTrue(observed['observed_complete_stop_before_line'])
            self.assertEqual(2, observed['native_frames'])
            self.assertEqual(set(VIEWS), set(observed['saved_camera_sources']))
            self.assertFalse(observed['physical_visibility_reviewed'])
            self.assertIsNone(observed['legal_verdict'])
            with self.assertRaisesRegex(ValueError, 'confirmed original'):
                process_saved(root, source_kind='original_native')
            (root / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing saved source camera'):
                process_saved(root, source_kind='synthetic_native_sample')


if __name__ == '__main__':
    unittest.main()
