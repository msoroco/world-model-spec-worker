import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preparing_hand_signal_rig import BONES, check_survey, request_hand_signal, spawn


class Driver:
    def __init__(self):
        self.id = 71
        self.controls = []
        self.shown = False

    def apply_control(self, control):
        self.controls.append(control)

    def show_pose(self):
        self.shown = True

    def hide_pose(self):
        self.shown = False


class BoneControl:
    def __init__(self):
        self.bone_transforms = []


class HandSignalRigTest(unittest.TestCase):
    def setUp(self):
        self.actor = Driver()
        self.carla = types.SimpleNamespace(
            Location=lambda **kw: kw, Rotation=lambda **kw: kw,
            Transform=lambda *args, **kw: (args, kw),
            WalkerBoneControl=BoneControl)
        self.survey = {"source_kind": "original_native_site_survey",
                       "driver_blueprint": "walker.pedestrian.0001",
                       "driver_spawn_xyz_yaw_deg": [150, 0.5, 0.5, 0],
                       "driver_vehicle_identity_source_id": "original:driver-vehicle",
                       "hand_signal_pose_source_id": "original:hand-pose",
                       "driver_window_visibility_source_id": "original:window"}
        self.world = types.SimpleNamespace(
            get_blueprint_library=lambda: types.SimpleNamespace(find=lambda name: name),
            try_spawn_actor=lambda blueprint, pose: self.actor)

    def test_source_bound_spawn_and_visible_pose_request(self):
        self.assertFalse(check_survey(self.survey)["physical_visibility_claimed"])
        actor = spawn(self.world, self.carla, self.survey)
        request = request_hand_signal(actor, self.carla, active=True)
        self.assertEqual(request["driver_actor_id"], 71)
        self.assertEqual([name for name, _ in actor.controls[0].bone_transforms], list(BONES))
        self.assertTrue(actor.shown)
        self.assertFalse(request["visible_to_subject_confirmed"])

    def test_reset_before_activation(self):
        request_hand_signal(self.actor, self.carla, active=True)
        state = request_hand_signal(self.actor, self.carla, active=False)
        self.assertFalse(state["pose_requested"])
        self.assertFalse(self.actor.shown)

    def test_missing_original_driver_identity_rejected(self):
        self.survey.pop("driver_vehicle_identity_source_id")
        with self.assertRaisesRegex(ValueError, "Original driver"):
            spawn(self.world, self.carla, self.survey)

    def test_missing_bone_api_rejected(self):
        del self.carla.WalkerBoneControl
        with self.assertRaisesRegex(ValueError, "bone control unavailable"):
            request_hand_signal(self.actor, self.carla, active=True)


if __name__ == "__main__":
    unittest.main()
