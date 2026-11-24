"""Exercise CARLA bone-control calls without importing CARLA on the CPU host."""
import importlib.util
from pathlib import Path
import types
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'hand_signal_pose.py'
SPEC = importlib.util.spec_from_file_location('hand_signal_pose', SOURCE)
POSE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POSE)
RUNNER_SPEC = importlib.util.spec_from_file_location('hand_signal_runner', SOURCE.parent / 'hand_signal_runner.py')
RUNNER = importlib.util.module_from_spec(RUNNER_SPEC)
RUNNER_SPEC.loader.exec_module(RUNNER)


class FakeCarla:
    class Location:
        def __init__(self, **coordinates):
            self.__dict__.update(coordinates)

    class Rotation:
        def __init__(self, **angles):
            self.angles = angles

    class Transform:
        def __init__(self, location=None, rotation=None):
            if rotation is None:
                rotation = location
                location = None
            self.location = location
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
    def test_runner_keeps_source_stopped_until_signal_ends(self):
        config = {'requested_subsequent_emergency_speed_mps': 2}
        self.assertEqual([RUNNER.source_motion_request(frame, config)
                          for frame in (79, 80, 99, 100)], [0, 0, 0, -2])

    def test_proxy_spawn_uses_vehicle_geometry_and_walker_blueprint(self):
        calls = []
        vehicle = types.SimpleNamespace(get_transform=lambda: types.SimpleNamespace(
            location=types.SimpleNamespace(x=10, y=3, z=0),
            rotation=types.SimpleNamespace(yaw=180)))
        library = types.SimpleNamespace(find=lambda name: calls.append(('find', name)) or name)
        world = types.SimpleNamespace(get_blueprint_library=lambda: library,
                                      try_spawn_actor=lambda blueprint, pose: calls.append(('spawn', blueprint, pose)) or FakeWalker())
        POSE.spawn_source_driver_proxy(FakeCarla, world, vehicle, 'walker.pedestrian.0001')
        self.assertEqual(calls[0], ('find', 'walker.pedestrian.0001'))
        self.assertEqual((calls[1][2].location.x, calls[1][2].location.y,
                          calls[1][2].rotation.angles['yaw']), (10, 1.5, 180))

    def test_non_walker_source_driver_rejected(self):
        with self.assertRaisesRegex(ValueError, 'walker skeleton'):
            POSE.spawn_source_driver_proxy(FakeCarla, None, None, 'vehicle.tesla.model3')

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
