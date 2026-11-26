"""Synthetic CPU probes for source-join arithmetic, not physical evidence."""
from __future__ import annotations

import copy
import unittest

from saved_source import CAMERAS, EXPECTED_FRAMES, audit_comparison, measure_rows


def geometry():
    return {"native_map_sha256": "source-hash", "native_map_object_readback": True,
            "crosswalk": {"near_x_m": 0.0, "width_along_road_m": 3.6576,
                          "low_y_m": -3.5, "high_y_m": 3.5, "marked_yellow": True},
            "school_xing_sign": {"legend": "School-Xing", "native_map_object_present": True,
                                  "x_m": -35.0}}


def rows(occupied=True):
    native = []
    mapping = []
    for i in range(EXPECTED_FRAMES):
        # Engineering probe crosses x=0 at frame 240. These are test doubles,
        # never emitted as an original Native attempt or delivery proof.
        front = -12 + i * 0.05
        native.append({"native_frame": i + 1000, "time_s": i / 20,
                       "source_kind": "synthetic_test_double",
                       "ego_body_xy_m": [[front, -3], [front, -0.5],
                                         [front - 4, -0.5], [front - 4, -3]],
                       "person": {"actor_id": 11, "actor_kind": "walker",
                                  "center_x_m": 1.0,
                                  "center_y_m": -1.0 if occupied else -4.0,
                                  "velocity_y_mps": 0.5 if occupied else 0.0}})
        mapping.append({"native_frame": i + 1000, "video_frame": i,
                        "time_s": i / 20,
                        "camera_frames": {camera: i + 1000 for camera in CAMERAS}})
    return native, mapping


class SavedSourceProbe(unittest.TestCase):
    def test_occupied_and_cleared_comparison(self):
        one = measure_rows(*rows(True), geometry(), require_original=False)
        two = measure_rows(*rows(False), geometry(), require_original=False)
        self.assertTrue(one["entry"]["person_in_crosswalk"])
        self.assertFalse(two["entry"]["person_in_crosswalk"])
        one["case_id"] = "condition_a"
        two["case_id"] = "condition_b"
        self.assertEqual(audit_comparison(one, two)["case_ids"],
                         ["condition_a", "condition_b"])

    def test_synthetic_cannot_be_original(self):
        with self.assertRaisesRegex(ValueError, "synthetic sample"):
            measure_rows(*rows(), geometry())

    def test_camera_frame_mismatch_rejected(self):
        native, mapping = rows()
        mapping[240]["camera_frames"]["approach"] = 123
        with self.assertRaisesRegex(ValueError, "camera frame joins"):
            measure_rows(native, mapping, geometry(), require_original=False)

    def test_short_trace_rejected(self):
        native, mapping = rows()
        with self.assertRaisesRegex(ValueError, "Incomplete synchronized"):
            measure_rows(native[:-1], mapping, geometry(), require_original=False)

    def test_sign_distance_rejected(self):
        changed = copy.deepcopy(geometry())
        changed["school_xing_sign"]["x_m"] = -25.0
        with self.assertRaisesRegex(ValueError, "below 100 ft"):
            measure_rows(*rows(), changed, require_original=False)

    def test_wrong_comparison_rejected(self):
        first = measure_rows(*rows(True), geometry(), require_original=False)
        second = measure_rows(*rows(True), geometry(), require_original=False)
        first["case_id"] = "condition_a"
        second["case_id"] = "condition_b"
        with self.assertRaisesRegex(ValueError, "occupied versus cleared"):
            audit_comparison(first, second)


if __name__ == "__main__":
    unittest.main()
