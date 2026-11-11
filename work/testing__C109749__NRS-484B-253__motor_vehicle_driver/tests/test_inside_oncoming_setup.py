import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('inside_oncoming_setup', ROOT / 'inside_oncoming_setup.py')
inside = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inside)


def waypoint(x, *, lane=-1, junction=17, yaw=180, next_items=()):
    return NS(transform=NS(location=NS(x=x, y=0.0), rotation=NS(yaw=yaw)),
              is_junction=junction is not None, road_id=21, lane_id=lane,
              get_junction=lambda: NS(id=junction), next=lambda distance: list(next_items))


class Blueprint:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class World:
    def __init__(self, actor):
        self.actor = actor
        self.blueprint = Blueprint()
        self.spawned_at = None

    def get_blueprint_library(self):
        return NS(find=lambda blueprint_id: self.blueprint)

    def try_spawn_actor(self, blueprint, transform):
        self.spawned_at = transform
        return self.actor


class SequenceWorld:
    def __init__(self, actors):
        self.actors = iter(actors)
        self.spawns = []
        self.blueprints = []

    def get_blueprint_library(self):
        def find(blueprint_id):
            blueprint = Blueprint()
            self.blueprints.append((blueprint_id, blueprint))
            return blueprint
        return NS(find=find)

    def try_spawn_actor(self, blueprint, transform):
        self.spawns.append(transform)
        return next(self.actors)


class TrackedActor:
    def __init__(self):
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


class BodyActor:
    id = 91

    def __init__(self, x):
        self.x = x
        self.bounding_box = NS(get_world_vertices=lambda transform: [
            NS(x=x + dx, y=dy) for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1))])

    def get_transform(self):
        return NS(location=NS(x=self.x, y=0.0), rotation=NS(yaw=180))

    def get_velocity(self):
        return NS(x=-2.0, y=0.0, z=0.0)


class InsideOncomingSetupTests(unittest.TestCase):
    def test_spawns_same_lane_inside_selected_junction(self):
        wrong_lane = waypoint(-6.0, lane=-2)
        wrong_junction = waypoint(-6.0, junction=18)
        inside_waypoint = waypoint(-6.0)
        entry = waypoint(0.0, next_items=(wrong_lane, wrong_junction, inside_waypoint))
        selected = {'junction_id': 17, 'oncoming': {'entry': entry}}
        world = World(actor=object())
        actor = inside.spawn_inside_opposing(world, selected)
        self.assertIs(actor, world.actor)
        self.assertIs(world.spawned_at, inside_waypoint.transform)
        self.assertEqual(world.blueprint.attributes['role_name'], 'opposing_vehicle_inside_junction')

    def test_rejects_other_lane_or_junction_without_spawning(self):
        entry = waypoint(0.0, next_items=(waypoint(-6.0, lane=-2), waypoint(-6.0, junction=18)))
        selected = {'junction_id': 17, 'oncoming': {'entry': entry}}
        world = World(actor=object())
        with self.assertRaisesRegex(ValueError, 'No same-lane inside-junction'):
            inside.spawn_inside_opposing(world, selected)
        self.assertIsNone(world.spawned_at)
        selected['junction_id'] = 18
        with self.assertRaisesRegex(ValueError, 'not in the selected Native junction'):
            inside.inside_waypoint(selected)

    def test_rejects_wrong_heading_short_progress_and_failed_spawn(self):
        entry = waypoint(0.0, next_items=(waypoint(-6.0, yaw=90), waypoint(-1.0)))
        selected = {'junction_id': 17, 'oncoming': {'entry': entry}}
        with self.assertRaisesRegex(ValueError, 'No same-lane inside-junction'):
            inside.inside_waypoint(selected)
        entry.next = lambda distance: [waypoint(-6.0)]
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            inside.spawn_inside_opposing(World(actor=None), selected)

    def test_pair_places_ego_outside_and_cleans_up_failed_inside_spawn(self):
        entry = waypoint(0.0, next_items=(waypoint(-6.0),))
        ego_start = waypoint(0.0, lane=1, junction=None)
        selected = {'junction_id': 17, 'ego': {'outside': ego_start},
                    'oncoming': {'entry': entry}}
        ego, opposing = TrackedActor(), TrackedActor()
        world = SequenceWorld((ego, opposing))
        self.assertEqual(inside.spawn_inside_pair(world, selected), (ego, opposing))
        self.assertIs(world.spawns[0], ego_start.transform)
        self.assertEqual(world.blueprints[1][1].attributes['role_name'],
                         'opposing_vehicle_inside_junction')
        failed = TrackedActor()
        world = SequenceWorld((failed, None))
        with self.assertRaisesRegex(ValueError, 'Native spawn failed'):
            inside.spawn_inside_pair(world, selected)
        self.assertTrue(failed.destroyed)

    def test_complete_body_must_be_inside_junction_envelope(self):
        context = {'intersection_polygon_xy_m': [[-5, -4], [5, -4], [5, 4], [-5, 4]]}
        self.assertEqual(inside.verify_inside_body(BodyActor(0), context)['actor_id'], 91)
        with self.assertRaisesRegex(ValueError, 'complete body is outside'):
            inside.verify_inside_body(BodyActor(5), context)

    def test_inside_actor_waits_for_measured_subject_junction_presence(self):
        self.assertEqual(inside.opposing_target_speed(
            ego_body_seen_in_junction=False, authored_approach_speed_mps=5.0), 0.0)
        self.assertEqual(inside.opposing_target_speed(
            ego_body_seen_in_junction=True, authored_approach_speed_mps=5.0), 5.0)
        with self.assertRaisesRegex(ValueError, 'Measured subject junction presence'):
            inside.opposing_target_speed(
                ego_body_seen_in_junction=1, authored_approach_speed_mps=5.0)


if __name__ == '__main__':
    unittest.main()
