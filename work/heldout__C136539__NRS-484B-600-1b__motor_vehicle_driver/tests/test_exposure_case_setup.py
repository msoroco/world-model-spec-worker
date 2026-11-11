import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from exposure_case_setup import CASES, PREFIX, case_settings, exposed_transform_point, spawn_exposed
from test_narrow_exposure_route import route_map


class ExposureCaseSetupTests(unittest.TestCase):
    def config(self, suffix):
        speed, kind, lateral = CASES[suffix]
        return {'selected_case_id': PREFIX + suffix, 'law_id': 'NRS-484B-600-1b',
                'cell_id': 'C136539', 'actor': 'motor_vehicle_driver',
                'rate_hz': 20, 'frames': 160, 'duration_s': 8,
                'requested_speed_mps': speed,
                'exposed_kind': kind, 'outside_edge_m': lateral,
                'construction_probe_only': True}

    def test_six_exact_settings_and_identity_rejection(self):
        for suffix in CASES:
            self.assertEqual(case_settings(self.config(suffix))['case_id'], PREFIX + suffix)
        with self.assertRaisesRegex(ValueError, 'setting differs'):
            case_settings(dict(self.config('property_near'), outside_edge_m=2.0))
        with self.assertRaisesRegex(ValueError, 'masquerade'):
            case_settings(dict(self.config('property_near'), construction_probe_only=False))
        with self.assertRaisesRegex(ValueError, 'Unknown'):
            case_settings(dict(self.config('property_near'), selected_case_id=PREFIX + 'invented'))

    def test_near_far_placement_on_both_approaches(self):
        for direction in (1, -1):
            _, route = route_map(direction=direction)
            near = exposed_transform_point(route, outside_edge_m=.4)
            far = exposed_transform_point(route, outside_edge_m=2.0)
            self.assertGreater(near[1] * direction, 0)
            self.assertGreater(abs(far[1]), abs(near[1]))

    def test_real_spawn_calls_and_fixed_property_physics(self):
        _, route = route_map()
        route[8].transform.rotation = NS(yaw=0)
        spawned = []
        actor = NS(set_simulate_physics=lambda value: spawned.append(('physics', value)))
        world = NS(get_blueprint_library=lambda: NS(find=lambda value: value),
                   try_spawn_actor=lambda blueprint, transform: spawned.append((blueprint, transform)) or actor)
        carla = NS(Location=lambda *values: values, Transform=lambda location, rotation: (location, rotation))
        for suffix in ('moderate_person_exposure', 'property_near'):
            self.assertIs(spawn_exposed(world, carla, route, case_settings(self.config(suffix))), actor)
        self.assertEqual([entry[0] for entry in spawned if entry[0] != 'physics'],
                         ['walker.pedestrian.0001', 'vehicle.tesla.model3'])
        self.assertIn(('physics', False), spawned)
        world.try_spawn_actor = lambda *_: None
        with self.assertRaisesRegex(ValueError, 'spawn failed'):
            spawn_exposed(world, carla, route, case_settings(self.config('property_far')))
