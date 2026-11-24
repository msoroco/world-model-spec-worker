import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).resolve().parents[1] / "crosswalk_delivery.py"
spec = importlib.util.spec_from_file_location("crosswalk_delivery", MODULE)
delivery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(delivery)


def site():
    return {
        "map_sha256": "map", "crosswalk_source_sha256": "crosswalk",
        "crosswalk_id": "cw-1", "one_way_road_id": "road-1",
        "access_source_sha256": "access", "signal_source_sha256": "signal",
        "obstacle_source_sha256": "obstacles", "participant_source_sha256": "participants",
        "pedestrian_source_sha256": "pedestrian-source",
        "crosswalk_qualification": "native_crosswalk_readback",
        "pedestrian_access": True, "governing_signal": "pedestrian_walk",
        "crosswalk_width_m": 4, "entry_center": [0, 0], "exit_center": [10, 0],
    }


class Adapter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def spawn_pedestrian(self, point, crosswalk_id):
        self.calls.append(("spawn", point, crosswalk_id))
        return "walker"

    def set_pedestrian_route(self, walker, points):
        self.calls.append(("route", walker, points))
        if self.fail:
            raise RuntimeError("route failed")

    def destroy(self, walker):
        self.calls.append(("destroy", walker))


class CrosswalkDeliveryTest(unittest.TestCase):
    def test_right_and_left_half_geometry(self):
        s = site()
        self.assertEqual(delivery.waypoints(s, "right")[0], (0.0, -1.0))
        self.assertEqual(delivery.waypoints(s, "left")[0], (0.0, 1.0))
        s["entry_center"], s["exit_center"] = s["exit_center"], s["entry_center"]
        self.assertEqual(delivery.waypoints(s, "right")[0], (10.0, 1.0))

    def test_source_and_context_are_required(self):
        for key in ("crosswalk_source_sha256", "access_source_sha256",
                    "signal_source_sha256", "obstacle_source_sha256", "participant_source_sha256"):
            s = site()
            del s[key]
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, "missing site source"):
                delivery.validate_site(s)
        s = site()
        s["crosswalk_qualification"] = "paint_assumed"
        with self.assertRaisesRegex(ValueError, "qualification"):
            delivery.validate_site(s)

    def test_spawn_and_cleanup(self):
        a = Adapter()
        walker, points = delivery.spawn_walk(site(), "right", a)
        self.assertEqual(walker, "walker")
        self.assertEqual(a.calls[0][0], "spawn")
        self.assertEqual(a.calls[1][2], points)
        a = Adapter(fail=True)
        with self.assertRaisesRegex(RuntimeError, "route failed"):
            delivery.spawn_walk(site(), "right", a)
        self.assertEqual(a.calls[-1], ("destroy", "walker"))

    def test_original_measurement_and_missing_stream_rejection(self):
        samples = [{"frame": n, "elapsed_s": n * 0.05, "pedestrian_xy": [n, -1],
                    "pedestrian_id": "walker-1", "pedestrian_source_sha256": "pedestrian-source"}
                   for n in range(3)]
        obstacles = [{"frame": n, "source_sha256": "obstacles", "available_right_width_m": 1.5} for n in range(3)]
        participants = [{"frame": n, "source_sha256": "participants", "participants": []} for n in range(3)]
        result = delivery.measure(site(), samples, obstacles, participants)
        self.assertEqual(result["right_half_sample_count"], 3)
        self.assertEqual(result["legal_practicability"], "unresolved")
        with self.assertRaisesRegex(ValueError, "frame join"):
            delivery.measure(site(), samples, obstacles[:-1], participants)
        obstacles[1]["source_sha256"] = "wrong"
        with self.assertRaisesRegex(ValueError, "source binding"):
            delivery.measure(site(), samples, obstacles, participants)
        obstacles[1]["source_sha256"] = "obstacles"
        samples[1]["elapsed_s"] = 0.07
        with self.assertRaisesRegex(ValueError, "20 Hz"):
            delivery.measure(site(), samples, obstacles, participants)
        samples[1]["elapsed_s"] = 0.05
        samples[1]["pedestrian_id"] = "other-walker"
        with self.assertRaisesRegex(ValueError, "pedestrian identity"):
            delivery.measure(site(), samples, obstacles, participants)
        samples[1]["pedestrian_id"] = "walker-1"
        samples[1]["frame"] = 1.0
        with self.assertRaisesRegex(ValueError, "frame identity"):
            delivery.measure(site(), samples, obstacles, participants)

    def test_comparison_rejects_changed_fixed_source_and_verdict(self):
        original = {"site_source_sha256": "site", "fixed_sources": {"map_sha256": "map"},
                    "full_original_trace": [{"frame": 1}],
                    "legal_practicability": "unresolved"}
        other = dict(original)
        self.assertTrue(delivery.audit_pair(original, other, ["target_half"])["passed"])
        other["fixed_sources"] = {"map_sha256": "changed"}
        with self.assertRaisesRegex(ValueError, "fixed site"):
            delivery.audit_pair(original, other, ["target_half"])
        other["legal_practicability"] = "compliant"
        with self.assertRaisesRegex(ValueError, "unsupported practicability"):
            delivery.audit_pair(original, other, ["target_half"])


if __name__ == "__main__":
    unittest.main()
