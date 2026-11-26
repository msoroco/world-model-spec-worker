"""Source-gated warning and release requests retain observable readback."""

import unittest

from school_lane_controls import VARIANTS, control_schedule
from warning_actuation import WarningActuator


HUMAN = {"flag_blueprint_id": "static.prop.flag", "flag_parked_pose": "parked",
         "flag_warning_pose": "warning", "flag_go_pose": "go",
         "departure_velocity_xy_mps": [1.0, 0.0]}
DEVICE = {"warning_state": "Red", "released_state": "Off"}
CHILD = {"child_classification_source": "reviewed original visible child",
         "crossing_velocity_xy_mps": [0.0, 1.0]}


class Fake:
    def __init__(self):
        self.flag = None
        self.device = None
        self.human_moves = []
        self.child_moves = []

    def set_flag_pose(self, pose):
        self.flag = pose

    def read_flag_pose(self):
        return self.flag

    def set_device_state(self, state):
        self.device = state

    def read_device_state(self):
        return self.device

    def move_human(self, velocity):
        self.human_moves.append(velocity)

    def read_human_location(self):
        return [1, 2, 0]

    def move_child(self, velocity):
        self.child_moves.append(velocity)

    def read_child_location(self):
        return [3, 4, 0]


class ActuationTests(unittest.TestCase):
    def actuator(self, index):
        fake = Fake()
        return WarningActuator(control_schedule(VARIANTS[index], 100.0), HUMAN, DEVICE, CHILD, fake), fake

    def test_human_warning_then_go(self):
        actuator, fake = self.actuator(0)
        actuator.request(0)
        self.assertEqual(actuator.readback()["flag_pose"], "warning")
        actuator.request(500)
        self.assertEqual(fake.flag, "go")
        self.assertEqual(len(fake.child_moves), 1)
        self.assertEqual(actuator.readback()["legal_warning_or_release_judgment"], "unresolved")

    def test_departure_after_release(self):
        actuator, fake = self.actuator(4)
        actuator.request(499)
        self.assertFalse(fake.human_moves)
        actuator.request(500)
        self.assertEqual(fake.human_moves, [[1.0, 0.0]])

    def test_device_state_release(self):
        actuator, fake = self.actuator(6)
        actuator.request(0)
        self.assertEqual(fake.device, "Red")
        actuator.request(500)
        self.assertEqual(fake.device, "Off")

    def test_source_missing_rejected(self):
        with self.assertRaisesRegex(ValueError, "flag source missing"):
            WarningActuator(control_schedule(VARIANTS[0], 100.0), {}, DEVICE, CHILD, Fake())
        with self.assertRaisesRegex(ValueError, "child classification"):
            WarningActuator(control_schedule(VARIANTS[0], 100.0), HUMAN, DEVICE, {}, Fake())


if __name__ == "__main__":
    unittest.main()
