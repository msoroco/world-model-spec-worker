"""Source-derived CPU checks for the newly laid alternative."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))

from newly_laid_analyze import analyze_rows
from newly_laid_finalize import build_result, derive_channels, finalize
from newly_laid_recording_contract import CHANNELS, CASES, config
from test_analyze import source_rows
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_description

READBACK = {'warning_person_actor_id': 12,
            'plan': {'laid_polygon_xy_m': [[-1, -1], [1, -1],
                                             [1, 1], [-1, 1]]}}


def sample_analysis(case=CASES[0]):
    return {'case': case,
            'source_hashes': {name: 'a' * 64 for name in
                              ('native-actors.jsonl', 'video_frames.jsonl',
                               'live-readback.json')},
            'observations': {'source_frames': 600, 'source_elapsed_s': 30.0,
                             'pavement_footprint_contact_frames': [300],
                             'pavement_footprint_contact_observed': True,
                             'requested_footprint_contact_matched': True,
                             'warning_person_present_near_pavement_frames': 600}}


class NewlyLaidFinalizeTests(unittest.TestCase):
    def test_full_duration_measures_original_body_contact(self):
        frames, actors = source_rows()
        observed = analyze_rows(frames, actors, READBACK)
        self.assertEqual(observed['source_frames'], 600)
        self.assertAlmostEqual(observed['source_elapsed_s'], 30)
        self.assertEqual(observed['pavement_footprint_contact_frames'],
                         list(range(300, 600)))
        self.assertFalse(observed['newly_laid_pavement_verified'])

    def test_original_provenance_and_joins_are_required(self):
        frames, actors = source_rows()
        actors[3]['source_kind'] = 'synthetic_diagnostic_actor_and_map_readback'
        with self.assertRaisesRegex(ValueError, 'provenance'):
            analyze_rows(frames, actors, READBACK)
        frames, actors = source_rows()
        actors[3]['frame'] += 1
        with self.assertRaisesRegex(ValueError, 'frame join'):
            analyze_rows(frames, actors, READBACK)

    def test_native_result_schema_preserves_unverified_context(self):
        cfg = config(CASES[0], 600)
        recording_description(cfg['recording_description'])
        result = validate_result(build_result(cfg, sample_analysis()))
        self.assertEqual(len(result['recording_evidence']), len(CHANNELS) + 1)
        self.assertFalse(result['setup_confirmed'])
        self.assertFalse(result['maneuver_completed'])
        self.assertFalse(result['accepted'])
        self.assertIn('newly_laid_surface_unverified', result['physical_failure_flags'])

    def test_channels_come_from_retained_sources(self):
        frames, actors = source_rows(2)
        for actor in actors:
            actor.update(ego_position_xyz_m=[-5, 0, 0], ego_yaw_deg=0,
                         ego_velocity_xyz_mps=[1, 0, 0], ego_speed_mps=1,
                         ego_road_id=8, ego_lane_id=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            for name, rows in (('video_frames.jsonl', frames),
                               ('native-actors.jsonl', actors)):
                (path / name).write_text(''.join(json.dumps(row) + '\n'
                                                  for row in rows))
            (path / 'live-readback.json').write_text(json.dumps({
                'plan': dict(READBACK['plan'], map_name='surveyed-map'),
                'pavement_road_id': 8}))
            hashes = derive_channels(path, sample_analysis())
            self.assertEqual(set(hashes), set(CHANNELS))
            self.assertEqual(len((path / 'channels/ego_pose.jsonl').read_text().splitlines()), 2)

    def test_missing_raw_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'native-actors.jsonl').write_text('')
            (path / 'video_frames.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError, 'Missing required source: live-readback.json'):
                finalize(path, path / 'analysis-report.json')


if __name__ == '__main__':
    unittest.main()
