import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "native_signal.py"
SPEC = importlib.util.spec_from_file_location("c227824_native_signal", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Actor:
    def __init__(self, ident, kind, route="crossing-1", indication="other"):
        self.id = ident
        self.attributes = {kind: "true", "governs_pedestrian_route_id": route}
        if kind == "official_traffic_signal":
            self.attributes.update(signal_shape="circle", sole_illuminated="true")
        self.indication = indication
        self.frozen = False

    def get_state(self):
        return self.indication

    def set_state(self, value):
        self.indication = value

    def freeze(self, value):
        self.frozen = value

    def set_pedestrian_indication(self, value):
        self.indication = value

    def get_countdown(self):
        return 7


class World:
    def __init__(self, *actors):
        self.actors = {actor.id: actor for actor in actors}

    def get_actor(self, ident):
        return self.actors.get(ident)


class Carla:
    TrafficLightState = SimpleNamespace(Red="Red")


def scene(device="none"):
    return {"case_id": "testing__C227824__NRS-484B-307-8b__pedestrian__red_no_device_entry",
            "route_id": "crossing-1", "facing_head_id": 5,
            "governing_pedestrian_device_ids": [] if device == "none" else [8],
            "requested_pedestrian_indication": device,
            "device_inventory_review": {"complete": True, "source_sha256": "a" * 64}}


class NativeSignalTests(unittest.TestCase):
    def test_red_alone_binds_configures_and_samples_original_actor(self):
        head = Actor(5, "official_traffic_signal")
        s = scene()
        bound, others = MODULE.bind(World(head), s)
        receipt = MODULE.configure(bound, others, s, Carla)
        signal, devices = MODULE.sample(bound, others, s, frame=17, time_s=.85)
        self.assertTrue(head.frozen)
        self.assertTrue(receipt["original_readback_confirmed"])
        self.assertFalse(receipt["actual_pixels_verified"])
        self.assertEqual(signal["facing_traffic_signal"]["indication"], "steady_red_alone")
        self.assertEqual(devices["other_devices"], [])

    def test_walk_and_countdown_read_original_device(self):
        for requested in ("walk", "flashing_hand_countdown", "flashing_hand_no_countdown", "steady_hand"):
            head = Actor(5, "official_traffic_signal")
            other = Actor(8, "official_pedestrian_signal")
            s = scene(requested)
            bound, others = MODULE.bind(World(head, other), s)
            MODULE.configure(bound, others, s, Carla)
            signal, devices = MODULE.sample(bound, others, s, frame=17, time_s=.85)
            self.assertEqual(devices["other_devices"][0]["indication"], requested)
            if requested == "flashing_hand_countdown":
                self.assertEqual(devices["other_devices"][0]["countdown_s"], 7)

    def test_rejects_unreviewed_or_wrong_route_assets(self):
        s = scene("walk")
        s["device_inventory_review"]["complete"] = False
        with self.assertRaisesRegex(ValueError, "review missing"):
            MODULE.bind(World(Actor(5, "official_traffic_signal")), s)
        s = scene("walk")
        wrong = Actor(8, "official_pedestrian_signal", route="other")
        with self.assertRaisesRegex(ValueError, "official pedestrian device absent"):
            MODULE.bind(World(Actor(5, "official_traffic_signal"), wrong), s)

    def test_rejects_unreadable_countdown_and_nonred_frame(self):
        head = Actor(5, "official_traffic_signal")
        other = Actor(8, "official_pedestrian_signal")
        s = scene("flashing_hand_countdown")
        bound, others = MODULE.bind(World(head, other), s)
        MODULE.configure(bound, others, s, Carla)
        other.get_countdown = None
        with self.assertRaisesRegex(ValueError, "countdown readback unavailable"):
            MODULE.sample(bound, others, s, frame=17, time_s=.85)
        head.indication = "Green"
        with self.assertRaisesRegex(ValueError, "not red"):
            MODULE.sample(bound, others, s, frame=17, time_s=.85)


if __name__ == "__main__":
    unittest.main()
