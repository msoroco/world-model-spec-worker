"""Positive, incomplete and missing-source physical CPU probes."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from emergency_scene import scene_geometry
from physical_audit import assess_motion


def rows(direction: str, *, travel_m: float) -> list[dict]:
    geometry = scene_geometry(direction)
    sign = 1 if direction == "eastbound" else -1
    result = []
    for frame in range(900):
        result.append({"frame": frame, "native_frame": frame + 1,
                       "ego": {"actor_id": 11,
                               "x_m": geometry["ego_spawn_xy_m"][0] +
                               sign * travel_m * frame / 899,
                               "y_m": geometry["ego_spawn_xy_m"][1]},
                       "pedestrian": {"actor_id": 12,
                                      "x_m": geometry["pedestrian_spawn_xy_m"][0],
                                      "y_m": geometry["pedestrian_spawn_xy_m"][1]}})
    return result


class PhysicalAuditTests(unittest.TestCase):
    def test_both_approach_directions_complete(self):
        for direction in ("eastbound", "westbound"):
            with self.subTest(direction=direction):
                result = assess_motion(rows(direction, travel_m=85),
                                       {"approach": direction})
                self.assertEqual(result["status"], "met")
                self.assertGreater(result["passed_recipient_station_m"], 10)

    def test_stopped_approach_is_not_complete(self):
        result = assess_motion(rows("eastbound", travel_m=3),
                               {"approach": "eastbound"})
        self.assertEqual(result["status"], "not_met")

    def test_missing_evidence_is_unverified(self):
        result = assess_motion(None, {"approach": "eastbound"})
        self.assertEqual(result["status"], "unverified")

    def test_actor_identity_swap_rejected(self):
        trace = rows("eastbound", travel_m=85)
        trace[450]["ego"]["actor_id"] = 13
        with self.assertRaisesRegex(ValueError, "identity changed"):
            assess_motion(trace, {"approach": "eastbound"})


if __name__ == "__main__":
    unittest.main()
