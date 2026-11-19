import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from finalize_direction import finalize_attempt, process_saved, signal_case_id
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
            recording = {'channels': [{'name': name, 'unit': unit,
                'sampling_rate_hz': 20, 'method': 'saved Native source',
                'time_window': 'entire capture', 'reference_frame': 'Native',
                'uncertainty': '50 ms'} for name, unit in (
                    ('kin.velocity', 'm/s'), ('drv.stopped', 'boolean'),
                    ('dev.human_direction', 'structured'),
                    ('native_actor_state', 'structured'),
                    ('camera_frame_join', 'structured'),
                    ('ego_pose', 'structured'), ('ego_speed', 'm/s'),
                    ('bus_obeys_officer_direction', 'boolean'))], 'context_inputs': [],
                    'limitations': ['synthetic Native sample; no physical review']}
            _write_json(root / 'config.json', {
                'case_id': signal_case_id('reference'), 'case_suffix': 'reference',
                'direction': 1, 'rate_hz': 20, 'frames': 2,
                'actor': 'bus_driver',
                'recording_description': recording})
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
                             'station_m': station, 'lane_y_native_m': -1.75,
                             'heading_native_deg': 0.0,
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
            (root / 'capture').mkdir()
            (root / 'capture' / 'recorder_info.txt').write_text(
                'Frame 1\nCreate bus-1: vehicle.mitsubishi.fusorosa\n')
            _write_json(root / 'capture' / 'manifest.json',
                        {'extraction_confirmed': True, 'frames': 2})
            (root / 'trace.jsonl').write_text(''.join(json.dumps({
                'frame': m['native_frame'], 'time_s': m['time_s'],
                'position': {'x': b['station_m'], 'y': 0, 'z': 0},
                'heading_deg': 0, 'speed_mps': 0}) + '\n'
                for m, b in zip(maps, rows)))
            (root / 'capture' / 'evidence.jsonl').write_text(''.join(
                json.dumps({'original_frame': m['native_frame'],
                            'recording_time_s': m['time_s']}) + '\n' for m in maps))
            for name in VIEWS:
                size = '1920x1080' if name == 'overview' else '1280x720'
                subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                                '-f', 'lavfi', '-i', 'color=c=blue:s=' + size + ':r=20',
                                '-frames:v', '2', '-c:v', 'ffv1', str(root / (name + '.mkv'))],
                               check=True, timeout=30)
            observed = process_saved(root, source_kind='synthetic_native_sample')
            self.assertTrue(observed['observed_complete_stop_before_line'])
            self.assertEqual(2, observed['native_frames'])
            self.assertEqual(set(VIEWS), set(observed['saved_camera_sources']))
            self.assertFalse(observed['physical_visibility_reviewed'])
            self.assertIsNone(observed['legal_verdict'])
            observed_original = process_saved(root, source_kind='original_native')
            self.assertEqual('original_native', observed_original['source_kind'])
            (root / 'capture' / 'evidence.jsonl').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing required source: capture/evidence.jsonl'):
                finalize_attempt(root, root / 'analysis-report.json')
            (root / 'capture' / 'evidence.jsonl').write_text(''.join(
                json.dumps({'original_frame': m['native_frame'],
                            'recording_time_s': m['time_s']}) + '\n' for m in maps))
            signal_definition = (root / 'officer_signal_definition.json').read_text()
            (root / 'officer_signal_definition.json').unlink()
            with self.assertRaisesRegex(ValueError,
                    'Missing required source: officer_signal_definition.json'):
                finalize_attempt(root, root / 'analysis-report.json')
            (root / 'officer_signal_definition.json').write_text(signal_definition)
            report = finalize_attempt(root, root / 'analysis-report.json')
            result = json.loads((root / 'result.json').read_text())
            self.assertEqual(2, report['trace_frames'])
            self.assertEqual('synthetic_fixture', report['provenance_kind'])
            self.assertEqual('synthetic_native_sample',
                             result['measured_values']['officer_direction']['source_kind'])
            self.assertEqual(8, len(result['recording_evidence']))
            self.assertFalse(result['target_checks'][0]['physical_cause_confirmed'])
            from batch_pipeline.validation import recording_evidence
            recording_evidence(result, recording, lambda relative: root / relative)
            from worker_exchange.measurement_contract import verify_report
            contract = json.loads((Path(__file__).parent /
                'constructions/reference-measurement-contract.json').read_text())
            self.assertEqual(3, len(verify_report(contract, report, root)))
            with self.assertRaisesRegex(ValueError, 'Retain prior finalization'):
                finalize_attempt(root, root / 'analysis-report-2.json')
            (root / 'approach.mkv').unlink()
            with self.assertRaisesRegex(ValueError, 'Missing saved source camera'):
                process_saved(root, source_kind='synthetic_native_sample')


if __name__ == '__main__':
    unittest.main()
