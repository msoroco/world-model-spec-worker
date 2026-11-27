import unittest
from types import SimpleNamespace as N

from route_control import apply, command


class Carla:
    Vector3D = staticmethod(lambda **kw: N(**kw))


class Bicycle:
    id = 11
    type_id = "vehicle.bh.crossbike"

    def __init__(self):
        self.x, self.y = -45.0, -1.75
        self.velocity = N(x=0.0, y=0.0, z=0.0)

    def get_transform(self):
        return N(location=N(x=self.x, y=self.y))

    def set_target_velocity(self, velocity):
        self.velocity = velocity


class TestRouteControl(unittest.TestCase):
    def test_progresses_across_right_turn_from_original_pose(self):
        bicycle = Bicycle()
        prior = 0
        saw_turn = False
        finished = False
        for _ in range(600):
            row = apply(bicycle, Carla, prior_index=prior)
            prior = row["route_index"]
            bicycle.x += bicycle.velocity.x / 20
            bicycle.y += bicycle.velocity.y / 20
            saw_turn |= bicycle.x > -7 and bicycle.y < -3.5
            if row["route_end_reached"]:
                finished = True
                break
        self.assertTrue(saw_turn)
        self.assertTrue(finished)
        self.assertLess(bicycle.y, -31)

    def test_rejects_wrong_actor_or_off_route(self):
        bicycle = Bicycle()
        bicycle.type_id = "vehicle.moped"
        with self.assertRaisesRegex(ValueError, "Selected bicycle"):
            command(bicycle, prior_index=0)
        bicycle.type_id = "vehicle.bh.crossbike"
        bicycle.x = 30
        with self.assertRaisesRegex(ValueError, "left authored route"):
            command(bicycle, prior_index=0)


if __name__ == "__main__":
    unittest.main()
