import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


path = Path(__file__).resolve().parents[1] / 'source_measurement.py'
spec = importlib.util.spec_from_file_location('c179480_source_measurement', path)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class SourceMeasurementTest(unittest.TestCase):
    def rows(self):
        return [
            dict(frame=101, ego_speed_mps=3.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=4.0, following_gap_m=15.0),
            dict(frame=102, ego_speed_mps=0.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=2.0, following_gap_m=8.0),
            dict(frame=103, ego_speed_mps=0.0, ego_on_roadway=True,
                 ego_lane_overlap=True, following_speed_mps=0.0, following_gap_m=5.0),
        ]

    def write_sources(self, directory, rows):
        source = directory / 'native-actors.jsonl'
        mapping = directory / 'video_frames.jsonl'
        source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
        mapping.write_text(''.join(json.dumps(dict(video_frame=i,
                                                 carla_frame=row['frame'],
                                                 time_s=i / 20))+'\n'
                                   for i, row in enumerate(rows)))
        return source, mapping

    def test_original_frame_values_are_measured_without_legal_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, mapping = self.write_sources(Path(tmp), self.rows())
            result = module.analyze(source, mapping)
        self.assertEqual(result['roadway_lane_overlap_frames'], [102, 103])
        self.assertEqual(result['following_speed_drop_mps'], 4.0)
        self.assertEqual(result['following_min_gap_m'], 5.0)
        self.assertEqual(result['normal_reasonable_movement_impeded'],
                         'independent_original_source_review_required')

    def test_governing_control_requires_observed_ego_association(self):
        rows = self.rows()
        for index, row in enumerate(rows):
            row['governing_control_state'] = {
                'source_kind': 'original_carla_actor_and_map_readback',
                'control_actor_id': 501,
                'control_type_id': 'traffic.traffic_light',
                'control_state': 'TrafficLightState.Red',
                'ego_associated_control_id': 501 if index == 2 else None,
                'ego_at_control': index == 2,
            }
        with tempfile.TemporaryDirectory() as tmp:
            source, mapping = self.write_sources(Path(tmp), rows)
            result = module.analyze_control(source, mapping,
                                            expected_control_id=501)
            self.assertEqual(result['associated_red_frames'], [103])
            with self.assertRaisesRegex(ValueError, 'actor ID is missing'):
                module.analyze_control(source, mapping)
            self.assertEqual(result['compliance_with_law'],
                             'independent_original_source_review_required')
            rows[2]['governing_control_state']['ego_associated_control_id'] = 777
            source, mapping = self.write_sources(Path(tmp), rows)
            self.assertEqual(module.analyze_control(
                source, mapping, expected_control_id=501)['associated_red_frames'], [])
            rows[2]['governing_control_state']['control_actor_id'] = 777
            source, mapping = self.write_sources(Path(tmp), rows)
            with self.assertRaisesRegex(ValueError, 'surveyed actor'):
                module.analyze_control(source, mapping, expected_control_id=501)

    def test_missing_frame_or_source_field_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = self.rows()
            source, mapping = self.write_sources(Path(tmp), rows)
            rows[1]['frame'] = 105
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'frame join'):
                module.analyze(source, mapping)
            rows[1]['frame'] = 102
            del rows[1]['following_gap_m']
            source.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'source field'):
                module.analyze(source, mapping)

    def test_stale_or_missing_frame_map_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, mapping = self.write_sources(Path(tmp), self.rows())
            lines = mapping.read_text().splitlines()
            mapping.write_text('\n'.join(lines[:-1])+'\n')
            with self.assertRaisesRegex(ValueError, 'length differs'):
                module.analyze(source, mapping)

    def test_nonroadway_stop_does_not_claim_roadway_stop(self):
        rows = self.rows()
        for row in rows:
            row['ego_on_roadway'] = False
        result = module.measure(rows)
        self.assertTrue(result['complete_stop_observed'])
        self.assertEqual(result['roadway_stop_frames'], [])

    def test_safe_operation_requires_original_hazard_body_and_motion(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            rows = self.rows()
            for row in rows:
                row['hazard_state'] = dict(
                    source_kind='original_carla_actor_and_map_readback',
                    body_vertices_xyz_m=[[6.,-1.,0.],[6.,1.,0.],
                                         [10.,1.,0.],[10.,-1.,0.]],
                    velocity_xyz_mps=[0.,0.,0.],
                    position_xyz_m=[8.,0.,0.], speed_mps=0.,
                    ego_center_gap_m=8., on_driving_lane=True,
                    road_id=7, lane_id=-1)
            actor, mapping = self.write_sources(folder, rows)
            observed = module.analyze_hazard(actor,mapping)
            self.assertEqual(observed['minimum_ego_center_gap_m'],8.)
            self.assertEqual(observed['safe_operation_necessity'],
                             'independent_original_source_review_required')
            del rows[1]['hazard_state']['body_vertices_xyz_m']
            actor.write_text(''.join(json.dumps(row)+'\n' for row in rows))
            with self.assertRaisesRegex(ValueError,'hazard geometry'):
                module.analyze_hazard(actor,mapping)


if __name__ == '__main__':
    unittest.main()
