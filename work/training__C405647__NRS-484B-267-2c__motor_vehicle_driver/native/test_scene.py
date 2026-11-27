"""Verify the controlled physical request before any CARLA acquisition."""

import copy
import unittest

from scene import CASES, check_pair, request
from measure_readiness import CAMERA_DIMENSIONS
from from_original import convert


class SceneTest(unittest.TestCase):
    def test_exact_pair_and_profile(self):
        first, second = (request(case) for case in CASES)
        self.assertTrue(check_pair(first, second)["passed"])
        self.assertEqual([camera["name"] for camera in first["cameras"]],
                         ["overview", "approach", "reference_corner", "driver_reference"])
        self.assertEqual(first["frames"], 600)
        self.assertLessEqual(first["ego_start_xyz_m"][0] +
                             first["ego_cruise_speed_mps"] * first["duration_s"],
                             first["ego_destination_xy_m"][0])
        self.assertLess(first["emergency_motion_start_frame"],
                        first["ego_response_policy"]["brake_onset_frame"])
        self.assertEqual({camera["name"]: (camera["width"], camera["height"])
                          for camera in first["cameras"]}, CAMERA_DIMENSIONS)

    def test_changed_map_or_emergency_motion_rejected(self):
        first, second = (request(case) for case in CASES)
        for change in ({"source_map": first["source_map"].replace("shoulder", "driving")},
                       {"emergency_motion_start_frame": 200},
                       {"light_request": "none"}):
            altered = copy.deepcopy(second)
            altered.update(change)
            with self.assertRaisesRegex(ValueError, "requests changed"):
                check_pair(first, altered)

    def test_original_trace_conversion_and_source_rejections(self):
        frames, actors, review = [], [], []
        for index in range(600):
            native = 30 + index
            frames.append({"video_frame": index, "native_frame": native,
                           "time_s": index / 20})
            ego_x = -80 + index * .1
            actors.append({"frame": index, "native_frame": native,
                           "source_kind": "original_native_motion",
                           "ego_brake_request": .8 if index >= 180 else 0,
                           "ego_brake_observed": .8 if index >= 180 else 0,
                           "actors": {
                               "ego": {"native_speed_mps": 2,
                                       "native_body_xy_m": [[ego_x, 1], [ego_x + 1, 1],
                                                            [ego_x, 2], [ego_x + 1, 2]]},
                               "emergency": {"native_speed_mps": .5,
                                             "native_body_xy_m": [[15, 5], [16, 5],
                                                                  [15, 6], [16, 6]]}}})
            review.append({"video_frame": index, "source_native_frame": native,
                           "source_camera": "approach",
                           "emergency_flashing_visible": index >= 150,
                           "emergency_motion_visible": index >= 150,
                           "hand_signal_visible": False})
        trace = convert(frames, actors, review)
        self.assertEqual(len(trace), 600)
        self.assertGreater(trace[0]["surface_gap_m"], trace[-1]["surface_gap_m"])
        self.assertEqual(trace[180]["ego_brake"], .8)
        stale = copy.deepcopy(review)
        stale[150]["source_native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "pixel source"):
            convert(frames, actors, stale)
        wrong_camera = copy.deepcopy(review)
        wrong_camera[150]["source_camera"] = "unrecorded_view"
        with self.assertRaisesRegex(ValueError, "pixel source"):
            convert(frames, actors, wrong_camera)
        fake = copy.deepcopy(actors)
        fake[150]["source_kind"] = "synthetic_native_sample"
        with self.assertRaisesRegex(ValueError, "original Native"):
            convert(frames, fake, review)
        absent_body = copy.deepcopy(actors)
        absent_body[150]["actors"]["emergency"].pop("native_body_xy_m")
        with self.assertRaisesRegex(ValueError, "body vertices"):
            convert(frames, absent_body, review)
        no_readback = copy.deepcopy(actors)
        no_readback[180].pop("ego_brake_observed")
        with self.assertRaisesRegex(ValueError, "brake readback"):
            convert(frames, no_readback, review)


if __name__ == "__main__":
    unittest.main()
