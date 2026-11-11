import json
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_rider_probe import CASE_ID, check_config
from rider_arm import RiderArm
from rider_route import control, select_left_turn


def map_with_turn(initial_yaw):
    points = []
    for i in range(16):
        yaw = initial_yaw if i < 9 else initial_yaw + 15 * (i - 8)
        point = NS(road_id=1, lane_id=1, is_junction=i >= 9,
                   transform=NS(location=NS(x=i * 2.5, y=0),
                                rotation=NS(yaw=yaw)))
        points.append(point)
    for i, point in enumerate(points):
        point.next = lambda step, i=i: [points[i + 1]] if i + 1 < len(points) else []
    return NS(get_spawn_points=lambda: [NS(location=points[0].transform.location)],
              get_waypoint=lambda loc: points[0]), points


class RiderProbeTests(unittest.TestCase):
    def test_exact_config_and_connected_turn_both_approaches(self):
        p = Path(__file__).resolve().parents[1] / 'probe-config.json'
        check_config(json.loads(p.read_text()))
        for yaw in (0, 180):
            world_map, points = map_with_turn(yaw)
            route = select_left_turn(world_map)
            self.assertIs(route[0], points[0])
            self.assertGreaterEqual(len(route), 15)
        bad, points = map_with_turn(0)
        points[4].next = lambda step: []
        with self.assertRaisesRegex(ValueError, 'No connected'):
            select_left_turn(bad)

    def test_feedback_control_east_and_west(self):
        east = control([0, 0], [1, 0], [1, 0], [5, 1])
        west = control([0, 0], [-1, 0], [-1, 0], [-5, -1])
        self.assertGreater(east['steer'], 0)
        self.assertGreater(west['steer'], 0)
        self.assertGreater(east['throttle'], 0)

    def test_native_bone_command_and_readback_calls(self):
        neutral = NS(location=NS(x=0), rotation=NS(pitch=0, yaw=0, roll=5))
        bone = NS(name='crl_arm__L', relative=neutral)
        class Walker:
            def __init__(self): self.blend = []
            def get_bones(self): return NS(bone_transforms=[bone])
            def set_bones(self, control): bone.relative = control.bone_transforms[0][1]
            def blend_pose(self, value): self.blend.append(value)
        walker = Walker()
        carla = NS(Transform=lambda location, rotation: NS(location=location, rotation=rotation),
                   Rotation=lambda **kwargs: NS(**kwargs),
                   WalkerBoneControlIn=lambda pairs: NS(bone_transforms=pairs))
        arm = RiderArm(walker, carla)
        arm.set_signal(True)
        self.assertEqual(arm.readback()['relative_roll_deg'], 75)
        arm.set_signal(False)
        self.assertEqual(walker.blend, [1, 0])


if __name__ == '__main__':
    unittest.main()
