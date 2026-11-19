import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

from test_saved_analysis import SavedAnalysisTest
from source_measurement import analyze, analyze_hazard


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location('c179480_native_finalize', root/'native_finalize.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeFinalizeTest(unittest.TestCase):
    def sources(self, folder):
        SavedAnalysisTest().sources(folder)
        actor = folder/'native-actors.jsonl'
        rows = [json.loads(line) for line in actor.read_text().splitlines()]
        for row in rows:
            speed = row['ego_speed_mps']
            row.update(source_kind='original_carla_actor_and_map_readback',
                       ego_velocity_xyz_mps=[speed, 0., 0.],
                       ego_body_vertices_xyz_m=[[-2.,-1.,0.],[-2.,1.,0.],
                                                [2.,1.,0.],[2.,-1.,0.]],
                       ego_x_m=0., ego_y_m=0., ego_yaw_deg=0.,
                       ego_body_lateral_min_m=-1., ego_body_lateral_max_m=1.,
                       driving_lane_width_m=3.7, driving_road_id=7,
                       driving_lane_id=-1, following_velocity_xyz_mps=[
                           row['following_speed_mps'],0.,0.],
                       following_x_m=-10., following_y_m=0.,
                       following_on_driving_lane=True)
        for index, row in enumerate(rows):
            row['video_frame'] = index
        actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        map_file = folder/'native-map-readback.json'
        map_file.write_text(json.dumps(dict(format='c179480-original-map-readback-v1',
                                            map_name='test-road', case='reference',
                                            road_id=7, lane_id=-1))+'\n')
        receipt_file = folder/'source-measurements.json'
        receipt = analyze(actor,folder/'video_frames.jsonl')
        receipt.update(format='c179480-source-measurements-v1',case='reference',
                       actor_source_sha256=module.sha256(actor),
                       frame_map_sha256=module.sha256(folder/'video_frames.jsonl'),
                       map_readback_sha256=module.sha256(map_file))
        receipt_file.write_text(json.dumps(receipt)+'\n')
        (folder/'config.json').write_text(json.dumps({
            'case_id': module.ASSIGNMENT+'__reference',
            'case_suffix': 'reference', 'law_id': 'NRS-484B-627-2',
            'rate_hz': 20, 'duration_s': 0.15,
            'recording_description': {'channels': [
                {'name': name, 'unit': 'structured'} for name in module.CHANNELS],
                'context_inputs': []}})+'\n')

    def safe_sources(self, folder):
        self.sources(folder)
        actor = folder/'native-actors.jsonl'
        rows = [json.loads(line) for line in actor.read_text().splitlines()]
        for row in rows:
            row['hazard_state'] = dict(
                source_kind='original_carla_actor_and_map_readback',
                body_vertices_xyz_m=[[6.,-1.,0.],[6.,1.,0.],
                                     [10.,1.,0.],[10.,-1.,0.]],
                velocity_xyz_mps=[0.,0.,0.], position_xyz_m=[8.,0.,0.],
                speed_mps=0., ego_center_gap_m=8., on_driving_lane=True,
                road_id=7, lane_id=-1)
        actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        map_path = folder/'native-map-readback.json'
        map_data = json.loads(map_path.read_text())
        map_data['case'] = 'safe_operation_stop'
        map_path.write_text(json.dumps(map_data)+'\n')
        receipt_path = folder/'source-measurements.json'
        receipt = json.loads(receipt_path.read_text())
        receipt.update(case='safe_operation_stop',
                       actor_source_sha256=module.sha256(actor),
                       map_readback_sha256=module.sha256(map_path),
                       hazard_observation=analyze_hazard(actor,folder/'video_frames.jsonl'))
        receipt_path.write_text(json.dumps(receipt)+'\n')
        config_path = folder/'config.json'
        config = json.loads(config_path.read_text())
        config['case_id'] = module.ASSIGNMENT+'__safe_operation_stop'
        config['case_suffix'] = 'safe_operation_stop'
        config['recording_description']['channels'].extend(
            {'name': name, 'unit': 'structured'}
            for name in ('hazard_actor_state','ego_hazard_gap_history'))
        config_path.write_text(json.dumps(config)+'\n')

    def test_safe_operation_finalizer_retains_hazard_without_necessity_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.safe_sources(folder)
            report = module.finalize(folder,folder/'analysis-report.json')
            result = json.loads((folder/'result.json').read_text())
            self.assertEqual(report['hazard_observation']['minimum_ego_center_gap_m'],8.)
            self.assertEqual(len(report['derived_channels']['channels']),12)
            self.assertIn('minimum_source_visible_hazard_gap',result['realized_observables'])
            self.assertIn('safe_operation_necessity_unreviewed',result['physical_failure_flags'])
            self.assertFalse(result['maneuver_completed'])
            self.assertFalse(result['legal_verdict_claimed'])

    def test_safe_operation_missing_hazard_rejected_before_derived_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.safe_sources(folder)
            actor = folder/'native-actors.jsonl'
            rows = [json.loads(line) for line in actor.read_text().splitlines()]
            del rows[1]['hazard_state']['body_vertices_xyz_m']
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'hazard geometry'):
                module.finalize(folder,folder/'analysis-report.json')
            self.assertFalse((folder/'result.json').exists())

    def test_native_shaped_result_retains_unverified_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            original = (folder/'native-actors.jsonl').read_bytes()
            report = module.finalize(folder, folder/'analysis-report.json')
            result = json.loads((folder/'result.json').read_text())
            self.assertEqual(report['source_frames'], 3)
            self.assertEqual(report['measurements']['roadway_stop']['method'],
                             'measure_roadway_stop')
            self.assertEqual(report['measurements']['paved_roadway_scope']['value']
                             ['road_id'], 7)
            self.assertEqual(len(report['derived_channels']['channels']), 10)
            self.assertEqual(result['measured_values']['normal_reasonable_movement_impeded'],
                             'independent_original_source_review_required')
            self.assertFalse(result['maneuver_completed'])
            self.assertFalse(result['setup_confirmed'])
            self.assertFalse(result['legal_verdict_claimed'])
            self.assertTrue(result['target_checks'][0]['matched'])
            self.assertEqual((folder/'native-actors.jsonl').read_bytes(),original)
            self.assertEqual(len((folder/'trace.jsonl').read_text().splitlines()),3)
            first_trace = json.loads((folder/'trace.jsonl').read_text().splitlines()[0])
            self.assertEqual(first_trace['position'], {'x':0.,'y':0.,'z':0.})
            self.assertEqual(first_trace['heading_deg'],0.)
            with self.assertRaisesRegex(ValueError,'Retain prior finalization'):
                module.finalize(folder,folder/'second-report.json')

    def test_explicit_synthetic_fixture_never_claims_original_velocity(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            provenance = {'provenance_kind': 'synthetic_fixture',
                          'diagnostic_fixture': True,
                          'speed_source': 'synthetic_native_sample',
                          'physical_acceptance_claimed': False}
            (folder/'acquisition-provenance.json').write_text(json.dumps(provenance)+'\n')
            actor = folder/'native-actors.jsonl'
            rows = [json.loads(line) for line in actor.read_text().splitlines()]
            for row in rows:
                row['source_kind'] = 'synthetic_native_sample'
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            receipt_path = folder/'source-measurements.json'
            receipt = json.loads(receipt_path.read_text())
            receipt['actor_source_sha256'] = module.sha256(actor)
            receipt_path.write_text(json.dumps(receipt)+'\n')
            receipt_path.unlink()  # Runtime removes fixture-provided derived receipts.
            report = module.finalize(folder,folder/'analysis-report.json')
            result = json.loads((folder/'result.json').read_text())
            trace = [json.loads(line) for line in (folder/'trace.jsonl').read_text().splitlines()]
            self.assertEqual(report['provenance_kind'],'synthetic_fixture')
            self.assertTrue(receipt_path.is_file())
            self.assertEqual(result['provenance_kind'],'synthetic_fixture')
            self.assertFalse(result['accepted'])
            self.assertFalse(result['maneuver_completed'])
            self.assertEqual({row['speed_provenance'] for row in trace},
                             {'synthetic_native_sample'})

    def test_synthetic_rows_without_explicit_provenance_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            actor = folder/'native-actors.jsonl'
            rows = [json.loads(line) for line in actor.read_text().splitlines()]
            rows[0]['source_kind'] = 'synthetic_native_sample'
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source'):
                module.finalize(folder,folder/'analysis-report.json')
            self.assertFalse((folder/'result.json').exists())

    def test_stale_map_case_rejected_before_derived_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            path = folder/'native-map-readback.json'
            map_data = json.loads(path.read_text())
            map_data['case'] = 'contrast'
            path.write_text(json.dumps(map_data)+'\n')
            with self.assertRaisesRegex(ValueError,'another case'):
                module.finalize(folder,folder/'analysis-report.json')
            self.assertFalse((folder/'result.json').exists())

    def test_actor_video_identity_rejected_before_derived_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            self.sources(folder)
            actor = folder/'native-actors.jsonl'
            rows = [json.loads(line) for line in actor.read_text().splitlines()]
            rows[1]['video_frame'] = 9
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'video-frame identity'):
                module.finalize(folder,folder/'analysis-report.json')
            self.assertFalse((folder/'result.json').exists())


if __name__ == '__main__':
    unittest.main()
