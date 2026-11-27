"""CPU acquisition proof for the three right-turn arm requests."""
import unittest
from types import SimpleNamespace as N

from rider_arm import BONES, BLUEPRINT, spawn_rider, step_rider


class Carla:
    @staticmethod
    def Location(**kw):
        return N(**kw)

    @staticmethod
    def Rotation(**kw):
        return N(**kw)

    @staticmethod
    def Transform(location=None, rotation=None):
        return N(location=location, rotation=rotation)

    @staticmethod
    def WalkerBoneControlIn(rows):
        return N(bone_transforms=rows)


class Bicycle:
    id = 11
    type_id = BLUEPRINT

    def get_transform(self):
        return Carla.Transform(Carla.Location(x=10.0, y=-4.0, z=0.0),
                               Carla.Rotation(yaw=90.0))


class Rider:
    id = 12

    def __init__(self):
        self.pose = None
        self.request = []
        self.shown = False

    def set_transform(self, pose):
        self.pose = pose

    def set_bones(self, control):
        self.request = control.bone_transforms

    def show_pose(self):
        self.shown = True

    def hide_pose(self):
        self.request = []
        self.shown = False

    def get_bones(self):
        return N(bone_transforms=[N(name=name, world=Carla.Transform(
            Carla.Location(x=10.0, y=-4.0, z=1.4)))
            for names in BONES.values() for name in names])


class World:
    def __init__(self):
        self.spawned = None

    def get_blueprint_library(self):
        return N(find=lambda name: name)

    def try_spawn_actor(self, blueprint, pose):
        self.spawned = (blueprint, pose)
        return Rider()


class TestRiderArm(unittest.TestCase):
    def test_distinct_rider_and_physical_pose_requests(self):
        bike, world = Bicycle(), World()
        rider = spawn_rider(world, Carla, bike, "walker.pedestrian.0001")
        self.assertNotEqual(rider.id, bike.id)
        self.assertEqual(world.spawned[1].location.z, 0.85)
        right = step_rider(Carla, bike, rider, method="right_horizontal", frame=100)
        self.assertEqual(right["requested_bones"], list(BONES["right_horizontal"]))
        self.assertEqual(right["bone_world_xyz_m"]["crl_hand__R"], [10.0, -4.0, 1.4])
        self.assertTrue(rider.shown)
        self.assertAlmostEqual(right["rider_world_xyz_m"][1], -4.12)
        left = step_rider(Carla, bike, rider, method="left_upward", frame=101)
        self.assertEqual(left["requested_bones"], list(BONES["left_upward"]))
        neutral = step_rider(Carla, bike, rider, method="none", frame=102)
        self.assertFalse(rider.shown)
        self.assertEqual(neutral["requested_bones"], [])
        self.assertFalse(neutral["physical_mount_verified"])
        self.assertFalse(neutral["arm_pixels_verified"])

    def test_rejects_wrong_machine_or_missing_readback(self):
        bike, rider = Bicycle(), Rider()
        bike.type_id = "vehicle.moped"
        with self.assertRaisesRegex(ValueError, "bicycle blueprint"):
            step_rider(Carla, bike, rider, method="right_horizontal", frame=10)
        bike.type_id = BLUEPRINT
        rider.get_bones = lambda: N(bone_transforms=[])
        with self.assertRaisesRegex(ValueError, "arm bones absent"):
            step_rider(Carla, bike, rider, method="right_horizontal", frame=10)

    def test_rejects_unavailable_articulation(self):
        rider = Rider()
        rider.set_bones = None
        with self.assertRaisesRegex(ValueError, "articulated rider control"):
            step_rider(Carla, Bicycle(), rider, method="right_horizontal", frame=10)


if __name__ == "__main__":
    unittest.main()
