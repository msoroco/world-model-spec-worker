"""Focused source-join and statutory-structure measurement checks."""

import unittest

from measure_structure import measure


def source(kind, start):
    context = {"source_kind": "original_native_structure_map_and_ray_readback",
               "structure_kind": kind, "approach_structure_x_m": start,
               "highway_centre_y_m": 0, "one_way_native_survey": False}
    for key in ("native_map_sha256", "structure_geometry_sha256",
                "road_direction_survey_sha256", "centreline_geometry_sha256",
                "vehicle_extent_sha256", "sight_ray_source_sha256"):
        context[key] = "a" * 64
    return context


def rows(start, left=False):
    entries = []
    for frame in range(600):
        front = start - 60 + frame * .12
        rear = front - 4
        low_y, high_y = (1, 2) if left else (-2, -1)
        entries.append({"video_frame": frame, "native_frame": frame + 100,
                        "time_s": frame / 20,
                        "source_cameras": {name: frame for name in (
                            "overview", "approach", "reference_corner", "driver_reference")},
                        "body_xy_m": [[rear, low_y], [rear, high_y],
                                      [front, low_y], [front, high_y]],
                        "observed_speed_mps": 2.4,
                        "incoming_lane_sight_ray": {"status": "blocked",
                            "clear_lower_bound_m": 4, "blocker_upper_bound_m": 5}})
    return entries


class StructureMeasurementTests(unittest.TestCase):
    def test_bridge_and_viaduct_have_source_bound_approaches(self):
        for kind, start in (("bridge", -30), ("viaduct", -30)):
            with self.subTest(kind=kind):
                right = measure(source(kind, start), rows(start))
                left = measure(source(kind, start), rows(start, left=True))
                self.assertGreater(right["within_100_ft_driving_frames"], 0)
                self.assertEqual(right["left_of_centre_within_zone_frames"], 0)
                self.assertGreater(left["left_and_blocked_within_zone_frames"], 0)
                self.assertEqual(left["legal_compliance"], "unassessed")

    def test_unsourced_kind_rejected(self):
        with self.assertRaisesRegex(ValueError, "source"):
            measure(source("tunnel", -30), rows(-30))

    def test_frame_join_rejected(self):
        entries = rows(-30)
        entries[4]["native_frame"] = 103
        with self.assertRaisesRegex(ValueError, "Native frame"):
            measure(source("bridge", -30), entries)

    def test_zone_without_approach_rejected(self):
        with self.assertRaisesRegex(ValueError, "No approach"):
            measure(source("viaduct", -300), rows(-30))


if __name__ == "__main__":
    unittest.main()
