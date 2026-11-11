from pathlib import Path
from types import SimpleNamespace as NS
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from closure_construction import closure_transforms, spawn_closure, ClosureSourceRecorder


class FakeCarla:
    @staticmethod
    def Location(**values):
        return NS(**values)

    @staticmethod
    def Transform(location, rotation):
        return NS(location=location, rotation=rotation)


def waypoint(direction=1):
    return NS(lane_width=4.0, transform=NS(
        location=NS(x=10.0, y=2.0 * direction, z=0.0),
        rotation='route-rotation',
        get_forward_vector=lambda: NS(x=direction, y=0.0)))


class ClosureTests(unittest.TestCase):
    def test_three_physical_points_span_right_half_in_both_directions(self):
        east = closure_transforms(FakeCarla, waypoint())
        west = closure_transforms(FakeCarla, waypoint(-1))
        self.assertEqual([round(t.location.y, 2) for t in east], [0.6, 2.0, 3.4])
        self.assertEqual([round(t.location.y, 2) for t in west], [-0.6, -2.0, -3.4])
        self.assertTrue(all(t.location.x == 10 for t in east + west))

    def test_spawn_readback_and_continuous_original_source(self):
        next_id = iter((11, 12, 13))
        world = NS(get_blueprint_library=lambda: NS(filter=lambda _: ['cone']),
                   try_spawn_actor=lambda blueprint, transform: NS(
                       id=next(next_id), type_id='static.prop.trafficcone01',
                       get_transform=lambda transform=transform: transform,
                       destroy=lambda: None))
        actors = spawn_closure(world, FakeCarla, waypoint())
        with tempfile.TemporaryDirectory() as directory:
            recorder = ClosureSourceRecorder(directory, actors)
            first = recorder.append(100, .0)
            second = recorder.append(101, .05)
            self.assertEqual([d['actor_id'] for d in first['devices']],
                             ['11', '12', '13'])
            self.assertFalse(second['authority_verified'])
            with self.assertRaisesRegex(ValueError, 'not continuous'):
                recorder.append(103, .1)
            recorder.close()
            rows = [json.loads(x) for x in (
                Path(directory) / 'closure_devices.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 2)

    def test_partial_spawn_destroys_owned_cones(self):
        destroyed = []
        spawned = []
        def try_spawn(_, transform):
            if len(spawned) == 1:
                return None
            actor = NS(id=1, destroy=lambda: destroyed.append(1))
            spawned.append(actor)
            return actor
        world = NS(get_blueprint_library=lambda: NS(filter=lambda _: ['cone']),
                   try_spawn_actor=try_spawn)
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            spawn_closure(world, FakeCarla, waypoint())
        self.assertEqual(destroyed, [1])


if __name__ == '__main__':
    unittest.main()
