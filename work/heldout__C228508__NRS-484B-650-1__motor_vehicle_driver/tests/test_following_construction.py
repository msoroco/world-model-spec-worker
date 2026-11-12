from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from following_construction import (PHASES, apply_feedback, feedback_control,
                                    offset_behind, phase_at,
                                    route_from_waypoints, spawn_pair,
                                    validate_schedule)


class Waypoint:
    def __init__(self, x, direction=1, road=1, lane=1, junction=False):
        self.x, self.direction = x, direction
        self.road_id, self.lane_id, self.is_junction = road, lane, junction
        self.transform = NS(location=NS(x=x, y=0.0))

    def next(self, step):
        return [Waypoint(self.x + self.direction * step, self.direction,
                         self.road_id, self.lane_id)]


class Vehicle:
    def __init__(self):
        self.destroyed = False
        self.controls = []

    def destroy(self):
        self.destroyed = True

    def get_transform(self):
        return NS(location=NS(x=0.0, y=0.0), rotation=NS(yaw=0.0))

    def get_velocity(self):
        return NS(x=3.0, y=0.0)

    def apply_control(self, command):
        self.controls.append(command)


class ConstructionTests(unittest.TestCase):
    def test_schedule_and_both_map_directions(self):
        self.assertTrue(validate_schedule())
        self.assertEqual(phase_at(200).label, 'first_closing_request')
        self.assertEqual(phase_at(600).label, 'second_closing_request')
        self.assertEqual(phase_at(450).label, 'separate_encounters')
        self.assertLess(PHASES[3].end_m - PHASES[1].start_m, 1609.344)
        for direction in (1, -1):
            route, distances = route_from_waypoints(Waypoint(0, direction))
            self.assertGreaterEqual(distances[-1], 1800)
            self.assertEqual(route[-1].transform.location.x, direction * 1800)
        class Fork(Waypoint):
            def next(self, step):
                return [Waypoint(step), Waypoint(step, road=1, lane=1)]
        with self.assertRaisesRegex(ValueError, 'unique continuous'):
            route_from_waypoints(Fork(0))

    def test_spawn_pair_and_rollback(self):
        created = []
        class World:
            def try_spawn_actor(self, blueprint, transform):
                item = Vehicle() if len(created) == 0 else None
                created.append((blueprint, transform, item))
                return item
        library = NS(find=lambda name: name)
        with self.assertRaisesRegex(ValueError, 'lead vehicle'):
            spawn_pair(World(), library, 'ego-position', 'lead-position')
        self.assertEqual(created[0][0], 'vehicle.tesla.model3')
        self.assertTrue(created[0][2].destroyed)

    def test_controller_and_geometry(self):
        east = feedback_control((0, 0), 0, (3, 0), (10, 2), 8)
        west = feedback_control((0, 0), 3.141592653589793,
                                (-3, 0), (-10, -2), 8)
        self.assertGreater(east['steer'], 0)
        self.assertGreater(west['steer'], 0)
        self.assertGreater(east['throttle'], 0)
        self.assertEqual(east['brake'], 0)
        braking = feedback_control((0, 0), 0, (15, 0), (10, 0), 8)
        self.assertGreater(braking['brake'], 0)
        self.assertEqual(braking['throttle'], 0)
        vehicle = Vehicle()
        carla = NS(VehicleControl=lambda **kwargs: kwargs)
        self.assertEqual(apply_feedback(vehicle, carla, (10, 0), 8),
                         vehicle.controls[0])
        carla.Location = lambda **kwargs: NS(**kwargs)
        carla.Transform = lambda location, rotation: NS(location=location,
                                                        rotation=rotation)
        east_transform = NS(location=NS(x=100, y=0, z=0), rotation=NS(yaw=0))
        west_transform = NS(location=NS(x=-100, y=0, z=0), rotation=NS(yaw=180))
        self.assertAlmostEqual(offset_behind(east_transform, 20, carla).location.x, 80)
        self.assertAlmostEqual(offset_behind(west_transform, 20, carla).location.x, -80)


if __name__ == '__main__':
    unittest.main()
