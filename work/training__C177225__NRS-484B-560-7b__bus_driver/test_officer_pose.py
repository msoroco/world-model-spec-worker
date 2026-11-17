import unittest
from types import SimpleNamespace

from officer_direction import OfficerStop
from officer_pose import ARM_BONE, step


class FakeWalker:
    def __init__(self, bones=(ARM_BONE,)):
        self.bones = bones
        self.calls = []

    def get_bones(self):
        return SimpleNamespace(bone_transforms=[(bone, object()) for bone in self.bones])

    def get_pose_from_animation(self):
        self.calls.append('copy_animation')

    def set_bones(self, pose):
        self.calls.append(('set_bones', pose.bone_transforms))

    def show_pose(self):
        self.calls.append('show_pose')

    def hide_pose(self):
        self.calls.append('hide_pose')


class FakeRotation:
    def __init__(self, **values):
        self.values = values


class FakeTransform:
    def __init__(self, **values):
        self.values = values


class FakeBoneControl:
    def __init__(self, bones):
        self.bone_transforms = bones


CARLA = SimpleNamespace(Rotation=FakeRotation, Transform=FakeTransform,
                        WalkerBoneControlIn=FakeBoneControl)


class OfficerPoseTest(unittest.TestCase):
    def signal(self):
        return OfficerStop('officer-1', 'bus-1', 1, 10, 12, 30,
                           'crossing-1', True)

    def test_timed_signal_uses_native_bone_control_and_readback(self):
        walker = FakeWalker()
        before = step(walker, CARLA, self.signal(), 11)
        during = step(walker, CARLA, self.signal(), 12)
        after = step(walker, CARLA, self.signal(), 31)
        self.assertFalse(before['governing'])
        self.assertTrue(during['governing'])
        self.assertFalse(after['governing'])
        self.assertEqual(2, walker.calls.count('hide_pose'))
        self.assertIn('show_pose', walker.calls)
        self.assertEqual(ARM_BONE, during['pose_bone_readback'])
        self.assertFalse(during['visual_comprehension_claimed'])
        self.assertEqual('authored_scenario_assumption',
                         during['authorization_provenance'])

    def test_missing_bone_or_api_fails(self):
        with self.assertRaisesRegex(ValueError, 'right-arm bone'):
            step(FakeWalker(bones=()), CARLA, self.signal(), 12)
        with self.assertRaisesRegex(ValueError, 'bone control API'):
            step(FakeWalker(), SimpleNamespace(), self.signal(), 12)


if __name__ == '__main__':
    unittest.main()
