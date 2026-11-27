"""Prove every frozen source term is emitted from retained original-shaped inputs."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from capture import derive_channels

NAMES = ('drv.speed_below_traffic', 'drv.queue_behind', 'drv.laned_roadway',
         'drv.extreme_lane', 'rel.occupies', 'drv.overtaking',
         'st.lane_adjacency')

class ChannelSourceTest(unittest.TestCase):
    def setUp(self):
        root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
        root.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='c132924-channels-', dir=root)
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        ego = {'x_m': 14.5, 'y_m': 0.0, 'speed_mps': 3.0,
               'body_vertices_native_m': [[14.4, 0, 0], [14.6, 0, 0],
                                          [14.4, 0.2, 0], [14.6, 0.2, 0]]}
        follower = {'x_m': 14.4, 'y_m': -1.0, 'speed_mps': 5.0}
        native = [{'native_frame': 2000+i, 'time_s': i/20,
                   'actors': {'ego': ego, 'follower': follower,
                              'slower_vehicle': {'x_m': 14.5, 'y_m': 2.0, 'speed_mps': 2.0}},
                   'pass_observation': {'slower_vehicle_ahead': True,
                                        'slower_vehicle_cleared': False,
                                        'source_actor_id': 303}} for i in range(600)]
        frames = [{'native_frame': 2000+i, 'video_frame': i, 'time_s': i/20,
                   'source_cameras': {name: 2000+i for name in
                                      ('overview', 'approach', 'reference_corner',
                                       'driver_reference')}} for i in range(600)]
        (self.path/'native.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in native))
        (self.path/'video_frames.jsonl').write_text(''.join(json.dumps(x)+'\n' for x in frames))
        (self.path/'geometry.json').write_text(json.dumps({
            'outer_right_lane_radius_m': [13, 16],
            'inner_left_lane_radius_m': [10, 13],
            'same_direction_marked_lanes_source': 'original-shaped survey fixture'})+'\n')

    def test_all_frozen_terms_have_600_source_values(self):
        channels = derive_channels(self.path)
        names = {x['name'] for x in channels}
        self.assertTrue(set(NAMES) <= names)
        for name in NAMES:
            path = self.path/'channels'/(name+'.jsonl')
            data = [json.loads(x) for x in path.read_text().splitlines()]
            self.assertEqual(len(data), 600)
            self.assertTrue(all(row['value'] for row in data))
        self.assertEqual(json.loads((self.path/'channels/drv.speed_below_traffic.jsonl').read_text().splitlines()[0])['value'],
                         {'ego': 3.0, 'follower': 5.0})

    def test_missing_native_rejected(self):
        (self.path/'native.jsonl').unlink()
        with self.assertRaises(FileNotFoundError):
            derive_channels(self.path)

    def test_missing_frame_join_rejected(self):
        (self.path/'video_frames.jsonl').unlink()
        with self.assertRaises(FileNotFoundError):
            derive_channels(self.path)

    def test_missing_lane_geometry_rejected(self):
        (self.path/'geometry.json').unlink()
        with self.assertRaises(FileNotFoundError):
            derive_channels(self.path)

if __name__ == '__main__':
    unittest.main()
