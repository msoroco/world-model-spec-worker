"""Exercise CARLA bone-control calls without importing CARLA on the CPU host."""
import importlib.util
from pathlib import Path
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'hand_signal_pose.py'
SPEC = importlib.util.spec_from_file_location('hand_signal_pose', SOURCE)
POSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POSE)


class FakeCarla:
    class Rotation:
        def __init__(self, **angles):
            self.angles = angles

    class Transform:
        def __init__(self, rotation):
            self.rotation = rotation

    class WalkerBoneControlIn:
        def __init__(self, transforms):
            self.bone_transforms = transforms


class FakeWalker:
    def __init__(self, missing=False):
        self.missing = missing
        self.calls = []

    def set_bones(self, control):
        self.calls.append(('set_bones', control))

    def show_pose(self):
        self.calls.append(('show_pose', None))

    def get_bones(self):
        names = [name for name, _ in self.calls[0][1].bone_transforms]
        if self.missing:
            names.pop()
        return types.SimpleNamespace(bone_transforms=[(name, None) for name in names])


class HandSignalPose(unittest.TestCase):
    def test_actual_pose_api_calls_and_readback(self):
        walker = FakeWalker()
        result = POSE.apply_hand_signal(FakeCarla, walker)
        self.assertEqual([name for name, _ in walker.calls], ['set_bones', 'show_pose'])
        self.assertIn('crl_hand__R', result['requested_bones'])
        self.assertFalse(result['visual_visibility_verified'])

    def test_missing_hand_readback_rejected(self):
        with self.assertRaisesRegex(ValueError, 'bones absent'):
            POSE.apply_hand_signal(FakeCarla, FakeWalker(missing=True))

    def test_unmodeled_side_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Select one modeled hand'):
            POSE.request_bones(FakeCarla, 'center')


if __name__ == '__main__':
    unittest.main()
