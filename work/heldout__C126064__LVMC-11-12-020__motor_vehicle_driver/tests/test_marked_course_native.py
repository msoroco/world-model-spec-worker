import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marked_course_native import control_step, place_markers, turn_targets


class Location:
    def __init__(self, x, y):
        self.x, self.y = x, y


class Transform:
    def __init__(self, x, y):
        self.location = Location(x, y)


class Actor:
    def __init__(self, transform, offset=0):
        self.transform, self.offset, self.destroyed = transform, offset, False

    def get_transform(self):
        return Transform(self.transform.location.x + self.offset, self.transform.location.y)

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self, junction=True, offset=0):
        self.junction, self.offset, self.actors = junction, offset, []

    def get_blueprint_library(self):
        return self

    def get_map(self):
        return self

    def find(self, name):
        assert name == 'static.prop.road_marker'
        return name

    def get_waypoint(self, location):
        return type('Waypoint', (), {'is_junction': self.junction})()

    def try_spawn_actor(self, blueprint, transform):
        actor = Actor(transform, self.offset)
        self.actors.append(actor)
        return actor


class NativeMarkerTests(unittest.TestCase):
    def source(self, root):
        p = root / 'authorized-course.json'
        p.write_text(json.dumps({'authority_document': 'reviewed city plan',
                                 'intersection_id': 'junction-7',
                                 'median_opening_with_intersecting_road': True,
                                 'markers': [{'x': 1, 'y': 2, 'z': 0, 'yaw': 90,
                                              'blueprint_id': 'static.prop.road_marker'}]}))
        return p, hashlib.sha256(p.read_bytes()).hexdigest()

    def test_actual_spawn_and_readback(self):
        with TemporaryDirectory() as td:
            p, digest = self.source(Path(td))
            world = World()
            result = place_markers(world, p, digest, lambda x, y, z, yaw: Transform(x, y))
            self.assertEqual(result['physical_marker_xy_m'], [[1.0, 2.0]])
            self.assertEqual(len(world.actors), 1)
            self.assertFalse(world.actors[0].destroyed)

    def test_source_junction_and_readback_rejection(self):
        with TemporaryDirectory() as td:
            p, digest = self.source(Path(td))
            with self.assertRaisesRegex(ValueError, 'hash changed'):
                place_markers(World(), p, '0' * 64, lambda x, y, z, yaw: Transform(x, y))
            with self.assertRaisesRegex(ValueError, 'junction'):
                place_markers(World(junction=False), p, digest, lambda x, y, z, yaw: Transform(x, y))
            world = World(offset=1)
            with self.assertRaisesRegex(ValueError, 'readback'):
                place_markers(world, p, digest, lambda x, y, z, yaw: Transform(x, y))
            self.assertTrue(world.actors[0].destroyed)

    def test_source_bound_compared_turn_targets(self):
        with TemporaryDirectory() as td:
            p, _ = self.source(Path(td))
            record = json.loads(p.read_text())
            record.update({
                'intersection_polygon_xy_m': [[0, 0], [10, 0], [10, 10], [0, 10]],
                'indicated_course_xy_m': [[-2, 5], [3, 5], [7, 7], [12, 7]],
                'divergent_course_xy_m': [[-2, 5], [3, 3], [7, 3], [12, 7]],
            })
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            world = World()
            result = turn_targets(world, p, digest, 'divergent_course',
                                  lambda x, y, z, yaw: Transform(x, y))
            self.assertEqual(result['targets_xy_m'][1], [3, 3])
            self.assertFalse(result['actual_turn_observed'])
            with self.assertRaisesRegex(ValueError, 'source hash changed'):
                turn_targets(world, p, '0'*64, 'indicated_course',
                             lambda x, y, z, yaw: Transform(x, y))
            record['divergent_course_xy_m'] = record['indicated_course_xy_m']
            p.write_text(json.dumps(record))
            digest = hashlib.sha256(p.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, 'no different target'):
                turn_targets(world, p, digest, 'divergent_course',
                             lambda x, y, z, yaw: Transform(x, y))
            with self.assertRaisesRegex(ValueError, 'junction'):
                turn_targets(World(junction=False), p, digest, 'indicated_course',
                             lambda x, y, z, yaw: Transform(x, y))

    def test_controller_steers_to_target_and_rejects_invalid_state(self):
        straight = control_step((0, 0), (1, 0), (0, 0), (5, 0))
        turn = control_step((0, 0), (1, 0), (0, 0), (5, 5))
        self.assertEqual(straight['steer'], 0)
        self.assertGreater(turn['steer'], 0)
        self.assertLessEqual(turn['throttle'], .4)
        with self.assertRaisesRegex(ValueError, 'engineering speed'):
            control_step((0, 0), (1, 0), (0, 0), (5, 0), target_speed_mps=20)


if __name__ == '__main__':
    unittest.main()
