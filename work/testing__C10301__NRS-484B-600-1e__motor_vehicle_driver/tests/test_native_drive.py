import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_drive import NativeDrive, construct_vehicle, validate_context


class Waypoint:
    def __init__(self, x):
        self.road_id, self.lane_id, self.is_junction = 4, -1, False
        self.transform = NS(location=NS(x=x, y=0))
        self.successors = []

    def next(self, step):
        return self.successors


class Vehicle:
    def __init__(self):
        self.destroyed = False
        self.commands = []
        self.pose = NS(location=NS(x=0, y=0), rotation=NS(yaw=0))
        self.velocity = NS(x=4, y=0, z=0)

    def get_transform(self): return self.pose
    def get_velocity(self): return self.velocity
    def apply_control(self, command): self.commands.append(command)
    def destroy(self): self.destroyed = True


class World:
    def __init__(self):
        nodes = [Waypoint(x) for x in (0, 5, 10, 15, 20)]
        for a, b in zip(nodes, nodes[1:]): a.successors = [b]
        self.start = NS(location=NS(x=0, y=0))
        self.mapping = NS(name="TownX", get_spawn_points=lambda: [self.start],
                          get_waypoint=lambda location, project_to_road=False: nodes[0])
        self.vehicle = Vehicle()
        self.spawned = []

    def get_map(self): return self.mapping
    def get_blueprint_library(self): return NS(find=lambda name: NS(id=name))
    def try_spawn_actor(self, blueprint, transform):
        self.spawned.append((blueprint.id, transform))
        return self.vehicle


CONTEXT = {"native_map_id": "TownX", "reviewed_road_id": 4, "reviewed_lane_id": -1,
           "minimum_length_m": 15, "subject_blueprint_id": "vehicle.test",
           "route_source": "native-map-reviewed", "alley_source": "road-authority-review",
           "access_aisle_source": "road-authority-review", "road_authority_source": "authority-review"}


class NativeDriveTests(unittest.TestCase):
    def test_native_spawn_control_and_cleanup(self):
        world = World()
        with construct_vehicle(world, CONTEXT) as (vehicle, corridor):
            self.assertEqual(world.spawned[0][0], "vehicle.test")
            drive = NativeDrive(corridor, 80, lambda **kw: NS(**kw))
            step = drive.step(vehicle)
            self.assertEqual(step["segment_index"], 0)
            self.assertGreater(vehicle.commands[-1].throttle, 0)
        self.assertTrue(world.vehicle.destroyed)

    def test_rejects_missing_road_authority_and_wrong_map(self):
        with self.assertRaisesRegex(ValueError, "road_authority_source"):
            validate_context({k: v for k, v in CONTEXT.items() if k != "road_authority_source"})
        world = World()
        wrong = dict(CONTEXT, native_map_id="OtherTown")
        with self.assertRaisesRegex(ValueError, "map identity"):
            with construct_vehicle(world, wrong): pass
        self.assertFalse(world.spawned)


if __name__ == "__main__":
    unittest.main()
