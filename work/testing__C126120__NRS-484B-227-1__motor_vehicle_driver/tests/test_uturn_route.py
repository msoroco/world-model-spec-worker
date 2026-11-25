import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('uturn_route', ROOT / 'uturn_route.py')
ROUTE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ROUTE)


def plan(suffix):
    return json.loads((ROOT / 'cases' / suffix / 'route-plan.json').read_text())


class RouteTests(unittest.TestCase):
    def test_both_routes_clear_barriers_and_return_opposite(self):
        for suffix, expected in (
                ('source_verified_single_movement_uturn', ['forward']),
                ('source_verified_multiple_movement_uturn', ['forward', 'reverse', 'forward'])):
            source = plan(suffix)
            measured = ROUTE.validate_plan(source['divider_context'], source['segments'],
                                           source['barrier_footprints_xy_m'],
                                           body_radius_m=source['body_radius_m'])
            self.assertEqual(measured['gear_sequence'], expected)
            self.assertEqual(abs(measured['turn_angle_degrees']), 180)
            self.assertTrue(measured['blocked_space_clearance'])
            self.assertEqual(measured['public_authority_judgment'], 'unresolved')

    def test_blocked_crossing_and_disconnected_reverse_rejected(self):
        source = plan('source_verified_single_movement_uturn')
        source['segments'][0]['waypoints_xy_m'][3] = [5, 0]
        with self.assertRaisesRegex(ValueError, 'divider outside opening'):
            ROUTE.validate_plan(source['divider_context'], source['segments'],
                                source['barrier_footprints_xy_m'], body_radius_m=.4)

    def test_encroachment_attempt_is_observable_without_barrier_collision(self):
        source = plan('divider_encroachment_before_opening_uturn')
        measured = ROUTE.validate_plan(source['divider_context'], source['segments'],
                                       source['barrier_footprints_xy_m'], body_radius_m=.4,
                                       outside_opening_expected=True)
        self.assertGreater(measured['outside_opening_area_m2'], 0)
        self.assertFalse(measured['blocked_space_clearance'])
        self.assertEqual(measured['legal_conclusion'], 'unresolved')
        with self.assertRaisesRegex(ValueError, 'divider outside opening'):
            ROUTE.validate_plan(source['divider_context'], source['segments'],
                                source['barrier_footprints_xy_m'], body_radius_m=.4)
        source = plan('source_verified_multiple_movement_uturn')
        source['segments'][1]['waypoints_xy_m'][0] = [17, -1]
        with self.assertRaisesRegex(ValueError, 'phases do not join'):
            ROUTE.validate_plan(source['divider_context'], source['segments'],
                                source['barrier_footprints_xy_m'], body_radius_m=.4)

    def test_native_controller_changes_gear_at_declared_phase(self):
        source = plan('source_verified_multiple_movement_uturn')
        controls = []
        vehicle = NS(get_transform=lambda: NS(location=NS(x=15, y=-1), rotation=NS(yaw=45)),
                     apply_control=controls.append)
        fake = NS(VehicleControl=lambda **kw: NS(**kw))
        controller = ROUTE.SegmentedController(source['segments'])
        controller.waypoint = len(source['segments'][0]['waypoints_xy_m']) - 1
        with patch.dict(sys.modules, {'carla': fake}):
            step = controller.step(vehicle)
        self.assertEqual(step['gear'], 'reverse')
        self.assertTrue(step['reverse'])
        self.assertTrue(controls[-1].reverse)


if __name__ == '__main__':
    unittest.main()
