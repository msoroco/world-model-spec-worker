import importlib.util
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as NS

spec = importlib.util.spec_from_file_location('native_signal', Path(__file__).resolve().parents[1] / 'native_signal.py')
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class Waypoint:
    def __init__(self, x, yaw, junction=None, next_waypoints=None, previous_waypoints=None,
                 y=0, road_id=1, lane_id=1):
        self.transform = NS(location=NS(x=x, y=y), rotation=NS(yaw=yaw))
        self.junction = junction
        self.next_waypoints = next_waypoints or []
        self.previous_waypoints = previous_waypoints or []
        self.road_id, self.lane_id = road_id, lane_id

    def get_junction(self):
        return NS(id=self.junction) if self.junction is not None else None

    def next(self, distance):
        return self.next_waypoints

    def previous(self, distance):
        return self.previous_waypoints


class Light:
    def __init__(self, actor_id, od_id, waypoint, state='Red'):
        self.id, self.od_id, self.waypoint, self.state = actor_id, od_id, waypoint, state
        self.ignore_set = False

    def get_opendrive_id(self): return self.od_id
    def get_affected_lane_waypoints(self): return [self.waypoint]
    def get_state(self): return self.state
    def set_state(self, state):
        if not self.ignore_set: self.state = state


def pair():
    east_end = Waypoint(80, 0, junction=17)
    west_end = Waypoint(-80, 180, junction=17)
    east = Waypoint(-12, 0, next_waypoints=[east_end], previous_waypoints=[Waypoint(-80, 0)])
    west = Waypoint(12, 180, next_waypoints=[west_end], previous_waypoints=[Waypoint(80, 180)])
    return Light(1, 'L-east', east), Light(2, 'L-west', west)


class TestNativeSignal(unittest.TestCase):
    def test_governed_opposite_lanes_and_routes(self):
        east, west = pair()
        selected = mod.discover_approaches([east, west], 'control inventory source')
        self.assertEqual({x.junction_id for x in selected.values()}, {17})
        self.assertEqual({x.opendrive_id for x in selected.values()}, {'L-east', 'L-west'})
        self.assertEqual(mod.route_for(selected['east'])[0].location.x, -80)
        self.assertEqual(mod.route_for(selected['west'])[1].location.x, -80)

    def test_missing_linkage_and_ambiguous_route_rejected(self):
        east, west = pair()
        with self.assertRaisesRegex(ValueError, 'official-control'):
            mod.discover_approaches([east, west], '')
        with self.assertRaisesRegex(ValueError, 'opposing'):
            mod.discover_approaches([east], 'source')
        selected = mod.discover_approaches([east, west], 'source')
        east.waypoint.previous_waypoints.append(Waypoint(-90, 0))
        with self.assertRaisesRegex(ValueError, 'ambiguous'):
            mod.route_for(selected['east'])

    def test_blink_readback_and_restore(self):
        east, _ = pair()
        states = NS(Yellow='Yellow', Off='Off')
        with mod.FlashController(east, states) as controller:
            self.assertEqual(controller.set_at(0)['native_light_state'], 'Yellow')
            self.assertEqual(controller.set_at(.25)['native_light_state'], 'Off')
            self.assertEqual(controller.set_at(.5)['native_light_state'], 'Yellow')
        self.assertEqual(east.state, 'Red')

    def test_failed_readback_rejected(self):
        east, _ = pair()
        states = NS(Yellow='Yellow', Off='Off')
        with mod.FlashController(east, states) as controller:
            east.ignore_set = True
            with self.assertRaisesRegex(ValueError, 'readback mismatch'):
                controller.set_at(0)
            east.ignore_set = False

    def test_perpendicular_crossing_uses_same_junction(self):
        north_end = Waypoint(0, 90, junction=17, y=65, road_id=2)
        north = Waypoint(0, 90, next_waypoints=[north_end],
                         previous_waypoints=[Waypoint(0, 90, y=-65, road_id=2)], road_id=2)
        world_map = NS(generate_waypoints=lambda step: [north])
        route = mod.crossing_route(world_map, 17)
        self.assertEqual((route['start'].location.y, route['end'].location.y), (-65, 65))
        self.assertEqual(route['road_id'], 2)
        with self.assertRaisesRegex(ValueError, 'perpendicular'):
            mod.crossing_route(world_map, 18)

    def test_native_construction_spawns_both_directions_and_crossing(self):
        east, west = pair()
        north_end = Waypoint(0, 90, junction=17, y=65, road_id=2)
        north = Waypoint(0, 90, next_waypoints=[north_end],
                         previous_waypoints=[Waypoint(0, 90, y=-65, road_id=2)], road_id=2)
        class World:
            def __init__(self): self.spawns = []
            def get_actors(self): return NS(filter=lambda pattern: [east, west])
            def get_map(self): return NS(generate_waypoints=lambda step: [north])
            def get_blueprint_library(self): return NS(find=lambda name: name)
            def try_spawn_actor(self, blueprint, transform):
                actor = NS(transform=transform, destroyed=False)
                actor.destroy = lambda: setattr(actor, 'destroyed', True)
                self.spawns.append(actor)
                return actor
        for direction in ('east', 'west'):
            world = World()
            case = NS(direction=direction, crossing_vehicle=True)
            scene = mod.construct_native(world, case, 'official-device record')
            self.assertEqual(len(world.spawns), 2)
            self.assertEqual(scene['selected'].direction, direction)
            self.assertEqual(scene['ego'].transform.location.x, -80 if direction=='east' else 80)
            self.assertEqual(scene['crossing'].transform.location.y, -65)

    def test_partial_native_spawn_is_destroyed(self):
        east, west = pair()
        north_end = Waypoint(0, 90, junction=17, y=65, road_id=2)
        north = Waypoint(0, 90, next_waypoints=[north_end],
                         previous_waypoints=[Waypoint(0, 90, y=-65, road_id=2)], road_id=2)
        owned = NS(destroyed=False)
        owned.destroy = lambda: setattr(owned, 'destroyed', True)
        count = [0]
        def spawn(blueprint, transform):
            count[0] += 1
            return owned if count[0] == 1 else None
        world = NS(get_actors=lambda: NS(filter=lambda pattern: [east, west]),
                   get_map=lambda: NS(generate_waypoints=lambda step: [north]),
                   get_blueprint_library=lambda: NS(find=lambda name: name),
                   try_spawn_actor=spawn)
        with self.assertRaisesRegex(ValueError, 'crossing Native actor spawn failed'):
            mod.construct_native(world, NS(direction='east', crossing_vehicle=True), 'source')
        self.assertTrue(owned.destroyed)


if __name__ == '__main__': unittest.main()
