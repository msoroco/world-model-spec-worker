import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location('c179480_native_channels', root/'native_channels.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class NativeChannelsTest(unittest.TestCase):
    def sources(self, folder):
        row = {'source_kind': 'original_carla_actor_and_map_readback',
               'frame': 101, 'ego_speed_mps': 2.0,
               'ego_velocity_xyz_mps': [2.0, 0.0, 0.0],
               'ego_body_vertices_xyz_m': [[-2., -1., 0.], [-2., 1., 0.],
                                            [2., 1., 0.], [2., -1., 0.]],
               'ego_x_m': 0.0, 'ego_y_m': 0.0, 'ego_yaw_deg': 0.0,
               'ego_on_roadway': True, 'ego_lane_overlap': True,
               'ego_body_lateral_min_m': -1.0, 'ego_body_lateral_max_m': 1.0,
               'driving_lane_width_m': 3.7, 'driving_road_id': 7,
               'driving_lane_id': -1, 'following_speed_mps': 3.0,
               'following_velocity_xyz_mps': [3.0, 0.0, 0.0],
               'following_x_m': -10.0, 'following_y_m': 0.0,
               'following_on_driving_lane': True,
               'following_gap_m': 10.0,
               'ego_associated_control_id': None,
               'scene_actor_inventory': {
                   'format': 'c179480-native-scene-inventory-v1',
                   'source_kind': 'original_carla_actor_and_map_readback',
                   'coverage': {'center': 'ego_actor_location', 'radius_m': 100.},
                   'actors': [{'actor_id': 1, 'type_id': 'vehicle.ego'}]}}
        later = dict(row, frame=102, ego_speed_mps=0.0,
                     ego_velocity_xyz_mps=[0., 0., 0.],
                     following_speed_mps=2.0,
                     following_velocity_xyz_mps=[2., 0., 0.])
        actor = folder/'native-actors.jsonl'
        actor.write_text(''.join(json.dumps(x)+'\n' for x in (row, later)))
        (folder/'video_frames.jsonl').write_text(''.join(
            json.dumps(dict(video_frame=i, carla_frame=101+i,
                            time_s=i/20))+'\n' for i in range(2)))
        (folder/'native-map-readback.json').write_text(json.dumps(
            dict(format='c179480-original-map-readback-v1', map_name='Town',
                 case='reference', road_id=7, lane_id=-1))+'\n')
        return actor

    def test_raw_channels_include_acceleration_and_preserve_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            actor = self.sources(folder)
            original = actor.read_bytes()
            result = module.derive(folder)
            self.assertEqual(result['frames'], 2)
            self.assertEqual(len(result['channels']), 13)
            hazard = json.loads((folder/'channels/hazard_actor_state.jsonl').read_text().splitlines()[0])
            self.assertFalse(hazard['value']['absence_claimed'])
            rows = [json.loads(x) for x in
                    (folder/'channels/following_actor_deceleration.jsonl').read_text().splitlines()]
            self.assertIsNone(rows[0]['value']['acceleration_mps2'])
            self.assertAlmostEqual(rows[1]['value']['acceleration_mps2'], -20.)
            interaction = [json.loads(x) for x in
                           (folder/'channels/traffic_effect_evidence.jsonl').read_text().splitlines()]
            self.assertEqual(interaction[0]['value']['following_gap_m'], 10.0)
            self.assertAlmostEqual(interaction[1]['value']['following_acceleration_mps2'], -20.)
            self.assertEqual(interaction[1]['value']['normal_reasonable_movement_impeded'],
                             'independent_original_source_review_required')
            self.assertEqual(actor.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                module.derive(folder)

    def test_missing_body_and_wrong_map_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            actor = self.sources(folder)
            rows = [json.loads(x) for x in actor.read_text().splitlines()]
            del rows[0]['ego_body_vertices_xyz_m']
            actor.write_text(''.join(json.dumps(x)+'\n' for x in rows))
            with self.assertRaisesRegex(ValueError, 'actor/map channel source'):
                module.derive(folder)
            self.sources(folder)
            map_file = folder/'native-map-readback.json'
            map_file.write_text(json.dumps(dict(format='c179480-original-map-readback-v1',
                                                map_name='Town', case='reference', road_id=8,
                                                lane_id=-1))+'\n')
            with self.assertRaisesRegex(ValueError, 'actor/map channel source'):
                module.derive(folder)


if __name__ == '__main__':
    unittest.main()
