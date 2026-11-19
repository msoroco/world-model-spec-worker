import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from variant_finalize import build_result, derive_channels, finalize, measurement_records
from variant_recording_contract import CHANNELS, config
from test_variant_analyze import READBACK, rows

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_description


def analysis(route='crossing', diagnostic=False):
    contact = route == 'crossing'
    return {'case': route, 'control_kind': 'barrier',
            'source_kind': ('synthetic_diagnostic_capture' if diagnostic
                            else 'original_carla_capture'),
            'source_hashes': {name: 'a' * 64 for name in
                              ('native-actors.jsonl', 'video_frames.jsonl', 'live-readback.json')},
            'observations': {'source_frames': 600, 'source_elapsed_s': 30,
                             'pavement_footprint_contact_frames': [300] if contact else [],
                             'pavement_footprint_contact_observed': contact,
                             'requested_footprint_contact_matched': True,
                             'control_actor_near_pavement_frames': 600}}


class VariantFinalizeTest(unittest.TestCase):
    def test_result_uses_pinned_schema_and_keeps_physical_claims_open(self):
        for route in ('crossing', 'avoidance'):
            for diagnostic in (False, True):
                cfg = config('barrier', route, 600)
                recording_description(cfg['recording_description'])
                result = validate_result(build_result(cfg, analysis(route, diagnostic)))
                self.assertEqual(len(result['recording_evidence']), len(CHANNELS) + 1)
                self.assertFalse(result['accepted'])
                self.assertFalse(result['setup_confirmed'])
                self.assertFalse(result['maneuver_completed'])
                self.assertEqual(result['diagnostic_fixture'], diagnostic)
                self.assertEqual(result['target_checks'][0]['matched'], True)

    def test_rejects_changed_case_binding(self):
        cfg = config('barrier', 'crossing', 600)
        cfg['case_id'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'recording contract'):
            build_result(cfg, analysis())

    def test_channels_derive_from_retained_rows_and_survey(self):
        frames, actors = rows(2)
        for actor in actors:
            actor.update(ego_yaw_deg=0, ego_velocity_xyz_mps=[5, 0, 0],
                         ego_road_id=8, ego_lane_id=1)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in frames))
            (path / 'native-actors.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in actors))
            readback = dict(READBACK, pavement_road_id=8,
                            plan=dict(READBACK['plan'], map_name='surveyed-map'))
            (path / 'live-readback.json').write_text(json.dumps(readback))
            hashes = derive_channels(path, analysis())
            self.assertEqual(set(hashes), set(CHANNELS))
            self.assertEqual(len((path / 'channels/control_actor_state.jsonl').read_text().splitlines()), 2)
            context = json.loads((path / 'recorded-context.json').read_text())
            self.assertFalse(context['surveyed_repair_region']['newly_repaired_status_verified'])

    def test_measurements_bind_sources_without_legal_verdict(self):
        measured = measurement_records(analysis())
        self.assertEqual(len(measured), 2)
        for row in measured.values():
            self.assertEqual(set(row['sources']),
                             {'native-actors.jsonl', 'video_frames.jsonl', 'live-readback.json'})
            self.assertFalse(row['value']['legal_verdict_claimed'])

    def test_missing_source_fails_before_finalization(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / 'native-actors.jsonl').write_text('')
            (path / 'video_frames.jsonl').write_text('')
            with self.assertRaisesRegex(ValueError, 'Missing required source: live-readback.json'):
                finalize(path, path / 'analysis-report.json')

    def test_diagnostic_full_finalization_from_retained_sources(self):
        frames, actors = rows(600, diagnostic=True)
        for actor in actors:
            actor.update(ego_yaw_deg=0, ego_velocity_xyz_mps=[5, 0, 0],
                         ego_road_id=8, ego_lane_id=1)
        trace = [{'frame': frame['carla_frame'], 'time_s': frame['time_s'],
                  'position_m': actor['ego_position_xyz_m'][:2],
                  'speed_mps': actor['ego_speed_mps'],
                  'speed_provenance': 'synthetic_native_sample'}
                 for frame, actor in zip(frames, actors)]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            readback = dict(READBACK, pavement_road_id=8,
                            plan=dict(READBACK['plan'], map_name='surveyed-map'))
            documents = {
                'config.json': config('barrier', 'crossing', 600),
                'capture-receipt.json': {'source_kind': 'synthetic_diagnostic_capture',
                                         'source_frames': 600, 'control_kind': 'barrier',
                                         'case': 'crossing'},
                'acquisition-provenance.json': {'provenance_kind': 'synthetic_fixture',
                                                'diagnostic_fixture': True},
                'live-readback.json': readback,
            }
            for name, document in documents.items():
                (path / name).write_text(json.dumps(document))
            for name, data in (('video_frames.jsonl', frames),
                               ('native-actors.jsonl', actors), ('trace.jsonl', trace)):
                (path / name).write_text(''.join(json.dumps(row) + '\n' for row in data))
            (path / 'road.xodr').write_text('<OpenDRIVE/>')
            with patch('variant_analyze.verify_media', return_value=[{'name': 'mocked_media'}]):
                report = finalize(path, path / 'analysis-report.json')
            result = json.loads((path / 'result.json').read_text())
            self.assertTrue(report['analysis_complete'])
            self.assertFalse(report['physical_acceptance_claimed'])
            self.assertFalse(report['legal_acceptance_claimed'])
            self.assertTrue(result['diagnostic_fixture'])
            self.assertEqual(result['realized_observables']['surveyed_pavement_contact_frames']['value'], 300)
            self.assertEqual(len((path / 'channels/ego_pose.jsonl').read_text().splitlines()), 600)


if __name__ == '__main__':
    unittest.main()
