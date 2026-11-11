from pathlib import Path
from types import SimpleNamespace as NS
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from overtake_measurement import measure
from overtake_source_capture import OvertakeSourceRecorder


def actor(identity, x, y):
    def transform():
        return NS(location=NS(x=actor_state.x, y=actor_state.y),
                  get_forward_vector=lambda: NS(x=1, y=0))
    def vertices(_):
        return [NS(x=actor_state.x + dx, y=actor_state.y + dy, z=z)
                for z in (0, 1) for dx, dy in ((-1, -1), (1, 1), (1, -1), (-1, 1))]
    actor_state = NS(id=identity, x=x, y=y, get_transform=transform)
    actor_state.bounding_box = NS(get_world_vertices=vertices)
    return actor_state


class OvertakeSourceTests(unittest.TestCase):
    def test_native_rows_feed_saved_overtake_measurement(self):
        ego, other = actor(1, 0, 3.5), actor(2, 10, 0)
        world_map = NS(get_waypoint=lambda _: NS(is_junction=False, road_id=9,
                           lane_id=2, transform=NS(get_forward_vector=lambda: NS(x=1, y=0))))
        with tempfile.TemporaryDirectory() as directory:
            recorder = OvertakeSourceRecorder(directory, ego, other, world_map)
            recorder.append(20, 1.)
            ego.x = 10
            recorder.append(21, 1.05)
            ego.x, ego.y = 20, 2.5
            recorder.append(22, 1.1)
            recorder.close()
            observation = measure(Path(directory) / 'participant_footprints.jsonl')
            self.assertEqual(observation['abreast_frames'], [21])
            self.assertEqual(observation['first_return_frame'], 22)
            self.assertGreater(observation['clearance_at_first_return_m'], 0)
            with self.assertRaises(FileExistsError):
                OvertakeSourceRecorder(directory, ego, other, world_map)


if __name__ == '__main__':
    unittest.main()
