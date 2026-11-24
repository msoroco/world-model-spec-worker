import importlib.util
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("door_carla_adapter_test", ROOT / "carla_adapter.py")
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


class Actor:
    def __init__(self, number):
        self.id = number
        self.is_alive = True
        self.door = None
        self.destroyed = False

    def open_door(self, door):
        self.door = door

    def get_location(self):
        return type("V", (), {"x": 4.0, "y": 2.0})()

    def get_velocity(self):
        return type("V", (), {"x": 2.0, "y": 0.0})()

    def destroy(self):
        self.destroyed = True


class World:
    def __init__(self):
        self.frame = 10

    def tick(self):
        self.frame += 1
        return self.frame

    def get_snapshot(self):
        return type("S", (), {"frame": self.frame, "timestamp": type("T", (), {"elapsed_seconds": self.frame / 20})()})()


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.actors = []

        def spawn(role, packet, variant):
            actor = Actor(len(self.actors) + 1)
            self.actors.append(actor)
            return actor

        self.commands = []
        self.adapter = mod.CarlaDoorAdapter(World(), type("Carla", (), {"VehicleDoor": type("Door", (), {"FL": "FL", "FR": "FR"})}),
                                            map_sha256=lambda: "a" * 64,
                                            actor_factory=spawn,
                                            driver_act_controller=lambda *args: self.commands.append(args) or True,
                                            original_observer=lambda frame, driver, parked, passing, pending: {
                                                "source_frame_id": frame, "selected_driver_id": str(driver.id),
                                                "observed_act": pending[0] if pending else "none",
                                                "act_side": pending[1] if pending else None,
                                                "passing_body_xy": [[3, 1], [5, 1]],
                                                "act_envelope_xy": [[1, 1], [2, 1]],
                                                "passing_response": {"brake": 0, "acceleration_mps2": 0}})
        self.adapter.configure_site({"map_sha256": "a" * 64, "loading_site_id": "fixture"},
                                    {"loading_site_id": "fixture"})
        self.parked = self.adapter.spawn_parked({})
        self.passing = self.adapter.spawn_passing({}, "overlap")
        self.driver = self.adapter.spawn_driver({})

    def tearDown(self):
        self.adapter.cleanup()

    def test_original_door_command_and_actor_readback(self):
        self.adapter.command_act(self.driver, self.parked, "open", "left")
        self.assertEqual(self.parked.door, "FL")
        frame, timestamp = self.adapter.tick()
        self.assertEqual((frame, timestamp), (11, .55))
        row = self.adapter.observe(frame, self.driver, self.parked, self.passing)
        self.assertEqual((row["observed_act"], row["passing_speed_mps"]), ("open", 2))

    def test_board_and_alight_need_controller(self):
        self.adapter.command_act(self.driver, self.parked, "board", "right")
        self.assertEqual(self.commands[-1][2:], ("board", "right"))
        self.adapter.command_act(self.driver, self.parked, "alight", "left")
        self.assertEqual(self.commands[-1][2:], ("alight", "left"))
        with self.assertRaisesRegex(ValueError, "identity"):
            self.adapter.observe(11, Actor(99), self.parked, self.passing)

    def test_cleanup_reverse_order(self):
        self.adapter.cleanup()
        self.assertTrue(all(actor.destroyed for actor in self.actors))
        self.assertEqual(self.adapter.owned, [])


if __name__ == "__main__":
    unittest.main()
