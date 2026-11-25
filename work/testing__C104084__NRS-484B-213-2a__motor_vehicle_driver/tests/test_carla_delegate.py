import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from carla_delegate import CarlaDelegate
from runner import run


class CarlaShapes:
    @staticmethod
    def Location(**values):
        return SimpleNamespace(**values)

    @staticmethod
    def Rotation(**values):
        return SimpleNamespace(**values)

    @staticmethod
    def Transform(location, rotation):
        return SimpleNamespace(location=location, rotation=rotation)

    @staticmethod
    def VehicleControl(**values):
        return SimpleNamespace(**values)


class DelegateTests(unittest.TestCase):
    def test_missing_reviewed_setup_rejected_before_world_access(self):
        delegate = CarlaDelegate(None, {'case_id': 'case'}, 'case', Path('unused'),
                                 carla_module=CarlaShapes)
        with self.assertRaisesRegex(ValueError, 'separately reviewed Native setup'):
            delegate.begin('case')

    def test_four_reviewed_camera_poses_required(self):
        packet = {'case_id': 'case', 'map_opendrive_sha256': 'a' * 64,
                  'native_setup': {'reviewed': True, 'reviewer': 'r',
                                   'source_citation': 'source',
                                   'map_opendrive_sha256': 'a' * 64,
                                   'ego': {'blueprint': 'vehicle.car', 'pose': [0]*6,
                                           'route': [[0, 0, 0], [10, 0, 0]],
                                           'target_speed_mps': 5},
                                   'other': {'blueprint': 'vehicle.car', 'pose': [0]*6,
                                             'route': [[0, 0, 0], [10, 0, 0]],
                                             'target_speed_mps': 5},
                                   'cameras': {}}}
        delegate = CarlaDelegate(None, packet, 'case', Path('unused'),
                                 carla_module=CarlaShapes)
        with self.assertRaisesRegex(ValueError, 'four reviewed original cameras'):
            delegate.begin('case')

    def test_runner_rejects_foreign_exact_case_before_world_access(self):
        from tempfile import TemporaryDirectory
        scratch = ROOT.parents[1] / '.runtime-work' / 'c104084-delegate-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=scratch) as folder:
            root = Path(folder)
            (root / 'attempt').mkdir()
            (root / 'packet.json').write_text(json.dumps({'case_id': 'foreign'}))
            with self.assertRaisesRegex(ValueError, 'reviewed Native packet and exact case differ'):
                run(None, root / 'packet.json', root, root / 'attempt', 'foreign')

    def test_reviewed_route_control_moves_until_endpoint(self):
        class Vehicle:
            def __init__(self, x):
                self.x = x
                self.control = None
            def get_location(self):
                return SimpleNamespace(x=self.x, y=0)
            def get_transform(self):
                return SimpleNamespace(rotation=SimpleNamespace(yaw=0))
            def get_velocity(self):
                return SimpleNamespace(x=0, y=0, z=0)
            def apply_control(self, control):
                self.control = control
        packet = {'native_setup': {'ego': {'route': [[0,0,0], [10,0,0]],
                                           'target_speed_mps': 5}}}
        delegate = CarlaDelegate(None, packet, 'case', Path('unused'),
                                 carla_module=CarlaShapes)
        delegate.ego = Vehicle(0)
        delegate._apply_reviewed_route('ego')
        self.assertGreater(delegate.ego.control.throttle, 0)
        delegate.ego.x = 10
        delegate._apply_reviewed_route('ego')
        self.assertEqual(delegate.ego.control.brake, 1)


if __name__ == '__main__':
    unittest.main()
