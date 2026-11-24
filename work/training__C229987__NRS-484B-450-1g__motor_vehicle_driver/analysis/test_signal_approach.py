"""CPU geometry and missing-source checks using invented raw-shaped samples."""

import unittest
from signal_approach import REQUIRED_CONTEXT, measure


ASSIGNMENT = "training__C229987__NRS-484B-450-1g__motor_vehicle_driver"


def fixture(front_edge_distance_m):
    front = -front_edge_distance_m
    rear = front - 4.5
    polygon = [
        {"x_m": rear, "y_m": -1}, {"x_m": front, "y_m": -1},
        {"x_m": front, "y_m": 1}, {"x_m": rear, "y_m": 1},
    ]
    return {
        "assignment_id": ASSIGNMENT,
        "source_kind": "native_raw_capture",
        "road_geometry": {
            "approach_origin": {"x_m": 0, "y_m": 0},
            "approach_tangent": {"x_m": 1, "y_m": 0},
        },
        "signal": {"roadside_position": {"x_m": 0, "y_m": 3}},
        "geometry_uncertainty_m": 0.05,
        "context_sources": {key: "raw/context.json" for key in REQUIRED_CONTEXT},
        "frames": [
            {"time_s": i / 20, "speed_mps": 0.0, "vehicle_footprint_xy_m": polygon}
            for i in range(20)
        ],
    }


class SignalApproachTest(unittest.TestCase):
    def test_25_30_35_foot_requested_positions_remain_measurements(self):
        for feet in (25, 30, 35):
            distance = feet * 0.3048
            output = measure(fixture(distance))
            self.assertAlmostEqual(output["frames"][0]["front_edge_to_signal_station_m"], distance)
            self.assertAlmostEqual(output["frames"][0]["centre_to_signal_station_m"], distance + 2.25)
            self.assertEqual(output["frames"][0]["approach_side_geometry"], "yes")
            self.assertEqual(output["stationary_sample_count"], 20)
            self.assertEqual(output["legal_verdict"], None)
            self.assertAlmostEqual(output["roadside_signal_offset_m"], 3)

    def test_missing_context_source_rejected(self):
        raw = fixture(8)
        del raw["context_sources"]["officer_direction_source"]
        with self.assertRaisesRegex(ValueError, "missing context source officer_direction_source"):
            measure(raw)

    def test_missing_raw_geometry_rejected(self):
        raw = fixture(8)
        del raw["frames"][0]["vehicle_footprint_xy_m"]
        with self.assertRaisesRegex(ValueError, "missing raw four-corner"):
            measure(raw)

    def test_derived_fixture_source_rejected(self):
        raw = fixture(8)
        raw["source_kind"] = "synthetic_derived_channels"
        with self.assertRaisesRegex(ValueError, "source_kind must be native_raw_capture"):
            measure(raw)

    def test_other_assignment_rejected(self):
        raw = fixture(8)
        raw["assignment_id"] = "another-assignment"
        with self.assertRaisesRegex(ValueError, "raw source binds another assignment"):
            measure(raw)

    def test_ambiguous_approach_geometry_preserved(self):
        output = measure(fixture(0.02))
        self.assertEqual(output["frames"][0]["approach_side_geometry"], "uncertain")


if __name__ == "__main__":
    unittest.main()
