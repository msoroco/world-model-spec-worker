"""The original Native bridge requires actual actor pose and body readback."""
import unittest

from native_output_bridge import participant


class NativeOutputBridgeTests(unittest.TestCase):
    def test_missing_actor_pose_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'pose readback absent'):
            participant({'actor_id': 7, 'vehicle_blueprint': 'vehicle.test',
                         'speed_mps': 0.0})

    def test_source_bound_actor_pose_is_preserved(self):
        source = {'actor_id': 7, 'vehicle_blueprint': 'vehicle.test',
                  'position_m': [1.0, 2.0, 0.0], 'heading_deg': 90.0,
                  'speed_mps': 0.0,
                  'body_vertices_m': [[0, 1], [2, 1], [2, 3], [0, 3]]}
        actual = participant(source)
        self.assertEqual(actual['position_m'], source['position_m'])
        self.assertEqual(actual['body_vertices_m'], source['body_vertices_m'])
        self.assertEqual(actual['speed_mps'], 0.0)
