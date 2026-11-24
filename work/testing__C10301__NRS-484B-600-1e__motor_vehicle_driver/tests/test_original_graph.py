import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from original_graph import collect


def vector(x=0.0, y=0.0, z=0.0):
    return SimpleNamespace(x=x, y=y, z=z)


class Actor:
    id = 17
    type_id = 'vehicle.diagnostic'
    is_alive = True

    def __init__(self):
        self.bounding_box = SimpleNamespace(
            location=vector(), extent=vector(1.0, 0.5, 0.5),
            get_world_vertices=lambda transform: [vector(float(i), 0.0, 0.0)
                                                  for i in range(8)])

    def get_transform(self):
        return SimpleNamespace(location=vector(),
                               rotation=SimpleNamespace(pitch=0.0, yaw=0.0,
                                                        roll=0.0),
                               get_forward_vector=lambda: vector(1.0, 0.0, 0.0))

    def get_velocity(self):
        return vector(20.0, 0.0, 0.0)


class OriginalGraphTests(unittest.TestCase):
    def test_live_snapshot_uses_original_actor_and_recording_clock(self):
        actor = Actor()
        world = SimpleNamespace(get_actors=lambda: [actor])
        snapshot = SimpleNamespace(frame=101,
                                   timestamp=SimpleNamespace(elapsed_seconds=9.05))
        graph = json.loads(collect(world, actor, snapshot,
                                   expected_frame=101,
                                   expected_time_s=9.05,
                                   recording_time_s=0.0))
        self.assertEqual(graph['metadata']['frame'], 101)
        self.assertEqual(graph['metadata']['simulation_time_s'], 0.0)
        self.assertEqual(graph['nodes'][0]['attributes']['actor_id'], 17)
        self.assertEqual(graph['nodes'][0]['attributes']['velocity_mps'],
                         [20.0, 0.0, 0.0])
        with self.assertRaisesRegex(ValueError, 'snapshot frame/time differs'):
            collect(world, actor, snapshot, expected_frame=102,
                    expected_time_s=9.05, recording_time_s=0.05)


if __name__ == '__main__':
    unittest.main()
