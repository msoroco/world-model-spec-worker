import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from yield_control_sources import ControlWriter, observe_controls


class Point:
    x = 1.
    y = 2.
    z = 3.


class Sign:
    id = 12
    type_id = 'traffic.yield'
    trigger_volume = type('Box', (), {'get_world_vertices': lambda self, transform:
                          [Point(), Point(), Point(), Point()]})()

    def get_transform(self):
        return type('Transform', (), {'location': Point()})()


class World:
    frame = 100
    actors = [Sign()]

    def get_snapshot(self):
        return type('Snapshot', (), {'frame': self.frame})()

    def get_actors(self):
        return self.actors

    def get_map(self):
        return self

    name = 'authored-yield-site'

    def get_crosswalks(self):
        return []


class ControlTests(unittest.TestCase):
    def test_retains_identity_trigger_and_unknown_visual_facts(self):
        world = World()
        row = observe_controls(world, 12, frame=100)
        self.assertEqual(row['yield_sign']['actor_id'], 12)
        self.assertEqual(len(row['yield_sign']['trigger_vertices_m']), 4)
        self.assertEqual(row['native_crosswalk_vertices_m'], [])
        self.assertIn('unverified', row['sign_face_legibility'])
        with tempfile.TemporaryDirectory() as directory:
            writer = ControlWriter(directory)
            writer.add(row)
            with self.assertRaisesRegex(ValueError, 'must increase'):
                writer.add(row)
            self.assertEqual(json.loads(Path(directory, 'control_inventory.jsonl').read_text())['frame'], 100)

    def test_rejects_stale_frame_and_missing_sign(self):
        world = World()
        with self.assertRaisesRegex(ValueError, 'frame differs'):
            observe_controls(world, 12, frame=99)
        with self.assertRaisesRegex(ValueError, 'disappeared'):
            observe_controls(world, 99, frame=100)
