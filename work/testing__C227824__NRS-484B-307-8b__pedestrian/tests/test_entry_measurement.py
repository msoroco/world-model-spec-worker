import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "entry_measurement.py"
SPEC = importlib.util.spec_from_file_location("c227824_entry_measurement", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

HIGHWAY = [[0, 0], [8, 0], [8, 8], [0, 8]]
OUTSIDE = [[-2, 3], [-1, 3], [-1, 4], [-2, 4]]
CONTACT = [[-1, 3], [0, 3], [0, 4], [-1, 4]]
INSIDE = [[1, 3], [2, 3], [2, 4], [1, 4]]


def row(frame, body, devices=None):
    return {"frame": frame, "time_s": frame * 0.05,
            "body_polygon_xy_m": body,
            "facing_traffic_signal": {"official": True, "indication": "steady_red_alone"},
            "other_devices": [] if devices is None else devices}


class EntryMeasurementTests(unittest.TestCase):
    def test_original_body_speed_uses_post_startup_samples(self):
        def sample(frame):
            x = 0.05 * frame if frame >= 121 else 0.0
            return {"frame": frame, "time_s": frame * .05,
                    "body_polygon_xy_m": [[x, 0], [x + 1, 0], [x + 1, 1], [x, 1]]}
        rows = [sample(frame) for frame in range(1, 241)]
        measured = MODULE.measure_walking_speed(rows)
        self.assertIsNotNone(measured)
        self.assertAlmostEqual(measured["value"], 1.0)
        self.assertEqual(measured["first_frame"], 121)
        self.assertFalse(measured["legal_permission_determined"])
        self.assertIsNone(MODULE.measure_walking_speed(rows[:3]))
        rows[180]["frame"] = 2000
        with self.assertRaisesRegex(ValueError, "frame/time"):
            MODULE.measure_walking_speed(rows)

    def test_boundary_contact_is_first_entry(self):
        measured = MODULE.measure_entry([row(1, OUTSIDE), row(2, CONTACT), row(3, INSIDE)], HIGHWAY)
        self.assertEqual(measured["first_entry"]["frame"], 2)
        self.assertFalse(measured["legal_permission_determined"])

    def test_entry_snapshot_keeps_independent_device(self):
        for indication in ("walk", "flashing_hand_no_countdown", "steady_hand"):
            device = {"official": True, "indication": indication}
            measured = MODULE.measure_entry([row(1, OUTSIDE), row(2, INSIDE, [device])], HIGHWAY)
            self.assertEqual(measured["first_entry"]["other_devices"], [device])
        countdown = {"official": True, "indication": "flashing_hand_countdown", "countdown_s": 7}
        measured = MODULE.measure_entry([row(1, OUTSIDE), row(2, INSIDE, [countdown])], HIGHWAY)
        self.assertEqual(measured["first_entry"]["other_devices"], [countdown])

    def test_no_entry_stays_distinct_from_permission(self):
        measured = MODULE.measure_entry([row(1, OUTSIDE), row(2, OUTSIDE)], HIGHWAY)
        self.assertIsNone(measured["first_entry"])
        self.assertFalse(measured["entry_observed"])

    def test_countdown_clearance_uses_original_frame_order(self):
        seven = {"official": True, "indication": "flashing_hand_countdown", "countdown_s": 7}
        zero = {"official": True, "indication": "flashing_hand_countdown", "countdown_s": 0}
        early = MODULE.measure_entry([row(1, OUTSIDE, [seven]), row(2, INSIDE, [seven]),
                                      row(3, OUTSIDE, [seven]), row(4, OUTSIDE, [zero])], HIGHWAY)
        self.assertTrue(early["cleared_before_countdown_zero"])
        late = MODULE.measure_entry([row(1, OUTSIDE, [seven]), row(2, INSIDE, [seven]),
                                     row(3, INSIDE, [zero]), row(4, OUTSIDE, [zero])], HIGHWAY)
        self.assertFalse(late["cleared_before_countdown_zero"])

    def test_rejects_missing_sources_and_initial_entry(self):
        with self.assertRaisesRegex(ValueError, "already inside"):
            MODULE.measure_entry([row(1, INSIDE)], HIGHWAY)
        with self.assertRaisesRegex(ValueError, "inventory missing"):
            sample = row(1, OUTSIDE)
            del sample["other_devices"]
            MODULE.measure_entry([sample], HIGHWAY)
        with self.assertRaisesRegex(ValueError, "countdown source"):
            MODULE.measure_entry([row(1, OUTSIDE), row(2, INSIDE, [{"official": True, "indication": "flashing_hand_countdown"}])], HIGHWAY)
        with self.assertRaisesRegex(ValueError, "strictly increasing"):
            MODULE.measure_entry([row(1, OUTSIDE), row(1, CONTACT)], HIGHWAY)


if __name__ == "__main__":
    unittest.main()
