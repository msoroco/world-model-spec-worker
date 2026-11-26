"""Exact role and release requests before original Native realization."""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from school_warning_scene import CASE_VARIANTS, scene_request, validate_request
from school_native_plan import plan


class ReleaseVariantRequests(unittest.TestCase):
    def test_all_statutory_release_requests_are_exact_and_30_seconds(self):
        self.assertEqual(len(CASE_VARIANTS), 8)
        for suffix, (distance, role, release) in CASE_VARIANTS.items():
            with self.subTest(case=suffix):
                request = scene_request(suffix)
                self.assertEqual(request["warning"]["role"], role)
                self.assertEqual(request["warning"]["requested_release_event"], release)
                self.assertEqual(request["planned_frames"], 600)
                self.assertEqual(len(plan(suffix)), 600)
                self.assertEqual(validate_request(request)["camera_count"], 4)
                self.assertEqual(round(-request["vehicle"]["requested_stop_center_x_m"] *
                                       3.280839895013123), round(distance))

    def test_human_warning_requires_human_actor(self):
        for suffix in ("flagman_go", "flagman_left", "person_go", "person_left"):
            with self.subTest(case=suffix):
                self.assertTrue(scene_request(suffix)["warning"]["blueprint"].startswith(
                    "walker.pedestrian."))
