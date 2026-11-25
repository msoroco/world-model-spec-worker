import copy
import importlib.util
from pathlib import Path
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "green_lane_measurement.py"
spec = importlib.util.spec_from_file_location("green_lane_measurement", SOURCE)
measurement = importlib.util.module_from_spec(spec)
spec.loader.exec_module(measurement)
SHA = "a" * 64


def frames(*, bus_lane="east", green=("east",), moving=True, spill=False):
    rows = []
    for frame in range(3):
        time = frame / 20
        y = 0 if bus_lane == "east" else 4
        half_width = 2.1 if spill else 1
        x = frame if moving else 0
        joined = {"frame": frame, "elapsed_seconds": time, "source_sha256": SHA}
        rows.append({"frame": frame, "elapsed_seconds": time,
                     "body": {**joined, "bus_heading_deg": 0.0, "bus_footprint": [
                         [x - 2, y - half_width], [x + 2, y - half_width],
                         [x + 2, y + half_width], [x - 2, y + half_width]]},
                     "lane_signals": {**joined, "faces_bus": True,
                                      "placement": "over_individual_lanes",
                                      "highway_id": "one-way-highway",
                                      "official_device_source_sha256": SHA,
                                      "lanes": [
                                          {"lane_id": lane, "direction": "bus_direction",
                                           "lateral_bounds_m": bounds,
                                           "head_heading_deg": 180.0,
                                           "symbol": "down_green_arrow" if lane in green else "dark"}
                                          for lane, bounds in (("east", [-2, 2]), ("west", [2, 6]))]},
                     "camera_frame": dict(joined)})
    return rows


class GreenLaneMeasurementTests(unittest.TestCase):
    def test_one_and_two_green_lanes_and_non_obligation(self):
        selected = measurement.measure(frames())
        self.assertEqual(selected["permission_observed_frames"], [0, 1, 2])
        self.assertEqual(selected["bus_moving_frames"], [1, 2])
        adjacent = measurement.measure(frames(bus_lane="west"))
        self.assertEqual(adjacent["permission_observed_frames"], [])
        both = measurement.measure(frames(bus_lane="west", green=("east", "west")))
        self.assertEqual(both["permission_observed_frames"], [0, 1, 2])
        standing = measurement.measure(frames(moving=False))
        self.assertEqual(standing["bus_moving_frames"], [])
        self.assertEqual(standing["permission_observed_frames"], [0, 1, 2])
        self.assertEqual(standing["legal_judgment"], "unresolved")

    def test_full_body_must_fit_in_indicated_lane(self):
        result = measurement.measure(frames(spill=True))
        self.assertEqual(result["permission_observed_frames"], [])
        self.assertEqual(result["frame_observations"][0]["full_body_lane_ids"], [])

    def test_lateral_drift_and_rotation_are_bus_motion(self):
        drifting = frames(moving=False)
        for point in drifting[1]["body"]["bus_footprint"]:
            point[1] += 0.2
        for point in drifting[2]["body"]["bus_footprint"]:
            point[1] += 0.2
        self.assertEqual(measurement.measure(drifting)["bus_moving_frames"], [1])
        with self.assertRaisesRegex(ValueError, "bus lane"):
            measurement.compare_permission_without_motion(frames(), drifting)
        turning = frames(moving=False)
        turning[1]["body"]["bus_footprint"] = [
            [-1.9, -1.1], [2.1, -0.9], [1.9, 1.1], [-2.1, 0.9]]
        turning[2]["body"]["bus_footprint"] = copy.deepcopy(
            turning[1]["body"]["bus_footprint"])
        self.assertEqual(measurement.measure(turning)["bus_moving_frames"], [1])

    def test_missing_or_changed_source_and_join_rejected(self):
        sample = frames()
        sample[1]["lane_signals"]["source_sha256"] = "invalid"
        with self.assertRaisesRegex(ValueError, "source hash"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["camera_frame"]["frame"] = 9
        with self.assertRaisesRegex(ValueError, "join"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["lane_signals"]["official_device_source_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "official device"):
            measurement.measure(sample)

    def test_lane_mapping_and_frame_custody_rejected(self):
        sample = frames()
        sample[1]["lane_signals"]["lanes"][1]["direction"] = "opposite"
        with self.assertRaisesRegex(ValueError, "same-direction"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["lane_signals"]["lanes"][1]["lateral_bounds_m"] = [1, 6]
        with self.assertRaisesRegex(ValueError, "bounds overlap"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["frame"] = 3
        with self.assertRaisesRegex(ValueError, "contiguous"):
            measurement.measure(sample)

    def test_facing_claim_requires_original_opposed_headings(self):
        sample = frames()
        sample[1]["lane_signals"]["lanes"][0]["head_heading_deg"] = 0.0
        with self.assertRaisesRegex(ValueError, "orientation does not face"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["body"]["bus_heading_deg"] = None
        with self.assertRaisesRegex(ValueError, "original bus heading"):
            measurement.measure(sample)
        sample = frames()
        sample[1]["lane_signals"]["lanes"][0]["head_heading_deg"] = 90.0
        with self.assertRaisesRegex(ValueError, "orientation does not face"):
            measurement.measure(sample)

    def test_controlled_second_green_arrow_comparison(self):
        dark = frames(bus_lane="west")
        green = frames(bus_lane="west", green=("east", "west"))
        result = measurement.compare_green_indication(dark, green, "west")
        self.assertEqual(result["dark_permission_frames"], [])
        self.assertEqual(result["green_permission_frames"], [0, 1, 2])
        changed_body = copy.deepcopy(green)
        changed_body[1]["body"]["bus_footprint"][0][0] -= 0.5
        with self.assertRaisesRegex(ValueError, "bus body motion"):
            measurement.compare_green_indication(dark, changed_body, "west")
        changed_other = copy.deepcopy(green)
        changed_other[1]["lane_signals"]["lanes"][0]["symbol"] = "dark"
        with self.assertRaisesRegex(ValueError, "unselected lane indication"):
            measurement.compare_green_indication(dark, changed_other, "west")

    def test_green_permission_does_not_require_bus_motion(self):
        moving = frames()
        standing = frames(moving=False)
        result = measurement.compare_permission_without_motion(moving, standing)
        self.assertEqual(result["standing_motion_frames"], [])
        self.assertEqual(result["permission_frames"], [0, 1, 2])
        changed_signal = copy.deepcopy(standing)
        changed_signal[1]["lane_signals"]["lanes"][0]["symbol"] = "dark"
        with self.assertRaisesRegex(ValueError, "green indications"):
            measurement.compare_permission_without_motion(moving, changed_signal)


if __name__ == "__main__":
    unittest.main()
