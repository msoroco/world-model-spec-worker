import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c157964_sub2_ego_controller',
                                             ROOT / 'officer_ego_controller.py')
CONTROL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROL)
PREFIX = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__'


class OfficerEgoControllerTests(unittest.TestCase):
    def test_go_hold_and_inactive_source_branches(self):
        go = PREFIX + 'officer_controls_go'
        hold = PREFIX + 'officer_controls_hold'
        inactive = PREFIX + 'officer_present_inactive'
        arguments = dict(other_inside=True, approaching_hazard=False,
                         current_speed_mps=0.0)
        self.assertFalse(CONTROL.command(go, 'stop', **arguments)['proceed'])
        self.assertTrue(CONTROL.command(go, 'go', **arguments)['proceed'])
        self.assertFalse(CONTROL.command(hold, 'stop', **arguments)['proceed'])
        self.assertFalse(CONTROL.command(inactive, 'none', **arguments)['proceed'])
        self.assertTrue(CONTROL.command(inactive, 'none', other_inside=False,
                                        approaching_hazard=False,
                                        current_speed_mps=0.0)['proceed'])
        self.assertFalse(CONTROL.command(inactive, 'none', other_inside=False,
                                         approaching_hazard=True,
                                         current_speed_mps=0.0)['proceed'])
        with self.assertRaisesRegex(ValueError, 'approaching-hazard source'):
            CONTROL.command(inactive, 'none', other_inside=False,
                            approaching_hazard=None, current_speed_mps=0.0)

    def test_native_vehicle_control_applied(self):
        applied = []
        actor = NS(id=211, apply_control=lambda value: applied.append(value))
        carla = NS(VehicleControl=lambda **values: NS(**values))
        selected = CONTROL.command(PREFIX + 'officer_controls_go', 'go',
                                   other_inside=True, approaching_hazard=False,
                                   current_speed_mps=0.0)
        report = CONTROL.apply_native(carla, actor, selected)
        self.assertTrue(report['native_control_applied'])
        self.assertEqual(report['actor_id'], 211)
        self.assertGreater(applied[0].throttle, 0)


if __name__ == '__main__':
    unittest.main()
