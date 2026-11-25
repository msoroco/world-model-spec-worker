import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('c157964_sub2_officer_direction',
                                             ROOT / 'officer_direction.py')
DIRECTION = importlib.util.module_from_spec(SPEC)
import sys
sys.modules[SPEC.name] = DIRECTION
SPEC.loader.exec_module(DIRECTION)
PREFIX = 'testing__C157964__NRS-484B-257-2__motor_vehicle_driver__'


class BoneActor:
    id = 301

    def __init__(self):
        self.rotations = {'arm': NS(pitch=0.0, yaw=0.0, roll=0.0)}
        self.blended = []

    def get_bones(self):
        return NS(bone_transforms=[(name, None, NS(rotation=rotation))
                                   for name, rotation in self.rotations.items()])

    def set_bones(self, control):
        for name, transform in control:
            self.rotations[name] = transform.rotation

    def blend_pose(self, weight):
        self.blended.append(weight)


class OfficerDirectionTests(unittest.TestCase):
    def test_three_exact_direction_programs(self):
        go = PREFIX + 'officer_controls_go'
        hold = PREFIX + 'officer_controls_hold'
        inactive = PREFIX + 'officer_present_inactive'
        self.assertEqual([p.direction for p in DIRECTION.phases(go, 20)], ['stop', 'go'])
        self.assertEqual([p.direction for p in DIRECTION.phases(hold, 20)], ['stop'])
        self.assertEqual([p.direction for p in DIRECTION.phases(inactive, 20)], ['none'])
        actor = BoneActor()
        self.assertEqual(DIRECTION.apply_direction(actor, None, inactive, 4, 20)['programmed_direction'], 'none')
        with self.assertRaisesRegex(ValueError, 'adapter missing'):
            DIRECTION.apply_direction(actor, None, go, 15, 20)

    def test_native_bone_application_readback_and_missing_bone(self):
        carla = NS(Rotation=lambda **angles: NS(**angles),
                   Transform=lambda **values: NS(**values),
                   WalkerBoneControl=lambda updates: updates)
        adapter = DIRECTION.native_bone_adapter(
            carla, {'arm': {'pitch': 80, 'yaw': 0, 'roll': 0}},
            {'arm': {'pitch': 0, 'yaw': 80, 'roll': 0}})
        actor = BoneActor()
        go = PREFIX + 'officer_controls_go'
        stop = DIRECTION.apply_direction(actor, adapter, go, 2, 20)
        proceed = DIRECTION.apply_direction(actor, adapter, go, 12, 20)
        self.assertEqual((stop['programmed_direction'], proceed['programmed_direction']), ('stop', 'go'))
        self.assertEqual(proceed['realized_bones']['arm']['yaw'], 80.0)
        self.assertEqual(actor.blended, [1.0, 1.0])
        missing = DIRECTION.native_bone_adapter(
            carla, {'other_arm': {'pitch': 80, 'yaw': 0, 'roll': 0}},
            {'other_arm': {'pitch': 0, 'yaw': 80, 'roll': 0}})
        with self.assertRaisesRegex(ValueError, 'lacks officer arm bones'):
            DIRECTION.apply_direction(actor, missing, go, 12, 20)

    def test_expanded_physical_sweep_cases_use_go_program(self):
        for judgment in (3, 5):
            for rank in range(3):
                case = f'c157964_sub2_judgment_{judgment}-{rank:04d}'
                self.assertEqual([p.direction for p in DIRECTION.phases(case, 20)],
                                 ['stop', 'go'])
        with self.assertRaisesRegex(ValueError, 'Unknown exact'):
            DIRECTION.phases('c157964_sub2_judgment_5-9999', 20)


if __name__ == '__main__':
    unittest.main()
