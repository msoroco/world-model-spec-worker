from pathlib import Path
import sys
from types import SimpleNamespace as Box
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from native_control import step


class Actor:
    def __init__(self, actor_id, speed=8.0):
        self.id = actor_id
        self.speed = speed
        self.controls = []

    def get_velocity(self):
        return Box(x=self.speed, y=0.0, z=0.0)

    def apply_control(self, control):
        self.controls.append(control)


def sample(speed=8.0, gap=30.0):
    return {"frame": 100, "source_frame": 100,
            "ego_speed_mps": speed, "leader_gap_m": gap,
            "source_ids": {"ego_actor_id": 1, "leader_actor_id": 2}}


class NativeControlTests(unittest.TestCase):
    def setUp(self):
        self.scene = Box(ego=Actor(1), leader=Actor(2),
                         targets={"ego_speed_mps": 10.0, "leader_speed_mps": 8.0})
        self.factory = lambda **fields: fields

    def test_both_actors_controlled_from_current_sample(self):
        result = step(self.scene, sample(), self.factory)
        self.assertGreater(self.scene.ego.controls[-1]["throttle"], 0)
        self.assertGreater(self.scene.leader.controls[-1]["throttle"], 0)
        self.assertEqual(result["source_frame"], 100)
        self.assertEqual(result["legal_judgment"], "unresolved")

    def test_low_gap_overrides_speed_request_with_brake(self):
        step(self.scene, sample(gap=3), self.factory)
        self.assertEqual(self.scene.ego.controls[-1]["brake"], 1.0)
        self.assertEqual(self.scene.ego.controls[-1]["throttle"], 0.0)

    def test_fast_actor_brakes_and_actor_swap_rejected(self):
        step(self.scene, sample(speed=12.0), self.factory)
        self.assertGreater(self.scene.ego.controls[-1]["brake"], 0)
        wrong = sample()
        wrong["source_ids"]["ego_actor_id"] = 99
        with self.assertRaisesRegex(ValueError, "actor IDs differ"):
            step(self.scene, wrong, self.factory)

    def test_invalid_source_observation_rejected(self):
        with self.assertRaisesRegex(ValueError, "observation invalid"):
            step(self.scene, sample(gap=float("nan")), self.factory)
        self.scene.leader.speed = float("nan")
        with self.assertRaisesRegex(ValueError, "velocity is invalid"):
            step(self.scene, sample(), self.factory)


if __name__ == "__main__":
    unittest.main()
