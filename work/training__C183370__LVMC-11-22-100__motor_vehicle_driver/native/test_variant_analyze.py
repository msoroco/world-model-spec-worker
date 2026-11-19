import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_analyze import source_rows
from variant_analyze import analyze, analyze_rows
from variant_recording_contract import config as variant_config


READBACK = {'control_actor_id': 12,
            'control_type_id': 'static.prop.trafficwarning',
            'plan': {'control_kind': 'barrier',
                     'repair_polygon_xy_m': [[-1, -1], [1, -1], [1, 1], [-1, 1]],
                     'cases': {'crossing': {'requested_pavement_crossing': True},
                               'avoidance': {'requested_pavement_crossing': False}}}}


def rows(count=600, diagnostic=False):
    frames, actors = source_rows(count)
    for actor in actors:
        actor.pop('warning_person_actor_id')
        actor.pop('warning_person_type_id')
        actor.pop('warning_person_xyz_m')
        actor['control_actor_id'] = 12
        actor['control_type_id'] = 'static.prop.trafficwarning'
        actor['control_xyz_m'] = [2, 0, 0]
        actor['ego_position_xyz_m'] = [0, 0, 0]
        actor['ego_speed_mps'] = 5
        if diagnostic:
            actor['source_kind'] = 'synthetic_diagnostic_actor_and_map_readback'
    return frames, actors


def write_jsonl(path, values):
    path.write_text(''.join(json.dumps(row) + '\n' for row in values))


class VariantAnalysisTest(unittest.TestCase):
    def test_contact_and_full_duration_from_retained_rows(self):
        frames, actors = rows()
        result = analyze_rows(frames, actors, READBACK)
        self.assertEqual(result['pavement_footprint_contact_frames'], list(range(300, 600)))
        self.assertEqual(result['source_frames'], 600)
        self.assertAlmostEqual(result['source_elapsed_s'], 30)
        self.assertFalse(result['control_content_verified'])

    def test_rejects_broken_join_actor_and_provenance(self):
        frames, actors = rows(599)
        with self.assertRaisesRegex(ValueError, '600 joined'):
            analyze_rows(frames, actors, READBACK)
        frames, actors = rows()
        actors[350]['frame'] += 1
        with self.assertRaisesRegex(ValueError, 'frame join'):
            analyze_rows(frames, actors, READBACK)
        frames, actors = rows()
        actors[350]['control_actor_id'] = 99
        with self.assertRaisesRegex(ValueError, 'identity'):
            analyze_rows(frames, actors, READBACK)
        frames, actors = rows(diagnostic=True)
        with self.assertRaisesRegex(ValueError, 'provenance'):
            analyze_rows(frames, actors, READBACK)
        self.assertEqual(analyze_rows(frames, actors, READBACK, diagnostic=True)['source_frames'], 600)

    def test_full_analysis_binds_trace_and_source_hashes(self):
        frames, actors = rows()
        trace = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                  'position_m': [0, 0], 'speed_mps': 5,
                  'speed_provenance': 'original_carla_velocity'} for frame in frames]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'config.json').write_text(json.dumps(variant_config('barrier', 'crossing', 600)))
            (path / 'capture-receipt.json').write_text(json.dumps({
                'source_kind': 'original_carla_capture', 'source_frames': 600,
                'control_kind': 'barrier', 'case': 'crossing'}))
            (path / 'acquisition-provenance.json').write_text(json.dumps({
                'provenance_kind': 'native', 'diagnostic_fixture': False}))
            (path / 'live-readback.json').write_text(json.dumps(READBACK))
            (path / 'road.xodr').write_text('<OpenDRIVE/>')
            write_jsonl(path / 'video_frames.jsonl', frames)
            write_jsonl(path / 'native-actors.jsonl', actors)
            write_jsonl(path / 'trace.jsonl', trace)
            with patch('variant_analyze.verify_media', return_value=[{'name': 'mocked_media'}]):
                result = analyze(path)
            self.assertEqual(result['source_kind'], 'original_carla_capture')
            self.assertEqual(result['observations']['source_frames'], 600)
            self.assertIn('native-actors.jsonl', result['source_hashes'])
            (path / 'source-analysis.json').unlink()
            trace[40]['speed_provenance'] = 'synthetic_native_sample'
            write_jsonl(path / 'trace.jsonl', trace)
            with self.assertRaisesRegex(ValueError, 'trace differs'):
                analyze(path)


if __name__ == '__main__':
    unittest.main()
