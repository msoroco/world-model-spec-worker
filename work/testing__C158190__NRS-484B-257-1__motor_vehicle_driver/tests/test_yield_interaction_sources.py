import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_interaction_sources import InteractionWriter, observe_interaction


class Point:
    def __init__(self, x=0, y=0, z=0):
        self.x, self.y, self.z = x, y, z


class Actor:
    def __init__(self, ident):
        self.id = ident
        self.type_id = 'vehicle.tesla.model3'
        self.bounding_box = type('Box', (), {'get_world_vertices': lambda self, transform:
                            [Point(i, 0, 0) for i in range(8)]})()

    def get_transform(self):
        return type('Transform', (), {'location': Point(0,0,0)})()


class World:
    frame = 100

    def get_snapshot(self):
        return type('Snapshot', (), {'frame': self.frame})()


class InteractionTests(unittest.TestCase):
    def test_retains_bodies_and_context_for_physical_check(self):
        world = World()
        row = observe_interaction(world, Actor(1), Actor(2), 100, 5.)
        self.assertEqual(len(row['ego']['body_vertices_m']), 8)
        self.assertEqual(row['through']['actor_id'], 2)
        with tempfile.TemporaryDirectory() as directory:
            writer = InteractionWriter(directory)
            writer.add(row)
            self.assertEqual(json.loads(Path(directory, 'interaction_history.jsonl').read_text())['frame'], 100)
            self.assertEqual(len(json.loads(Path(directory, 'control_context.json').read_text())['intersection_xy_m']), 4)
            with self.assertRaisesRegex(ValueError, 'Nonmonotone'):
                writer.add(row)

    def test_rejects_stale_world_frame(self):
        with self.assertRaisesRegex(ValueError, 'frame differs'):
            observe_interaction(World(), Actor(1), None, 99, 5.)
