import unittest

from delivery_audit import VIEW_ROLES, validate_review_view


class ProductionPixelReviewTest(unittest.TestCase):
    def setUp(self):
        self.mapping = [
            {"video_frame": i, "carla_frame": 100 + i, "time_s": i / 20}
            for i in range(3)
        ]
        role = VIEW_ROLES["overview"]
        self.item = {
            "video_sha256": "video", "decode_receipt_sha256": "receipt",
            "rgb_sequence_sha256": "rgb", "visibility_status": "visible",
            "required_role": role, "inspected_frame_count": 3,
            "reviewed_frames": [
                {**row, "observed_role": role, "visibility_status": "visible"}
                for row in self.mapping
            ],
        }

    def check(self):
        validate_review_view(self.item, "overview", "video", "receipt", "rgb",
                             self.mapping, diagnostic=False)

    def test_visible_source_bound_frames_pass(self):
        self.check()

    def test_unresolved_or_occluded_production_review_rejected(self):
        for status in ("unresolved", "occluded", "not_visible"):
            with self.subTest(status=status):
                self.item["visibility_status"] = status
                with self.assertRaisesRegex(ValueError, "absent or stale"):
                    self.check()

    def test_frame_identity_and_role_must_match_decode_join(self):
        for key, bad in (("carla_frame", 999), ("observed_role", "other"),
                         ("time_s", 99)):
            with self.subTest(key=key):
                original = self.item["reviewed_frames"][1][key]
                self.item["reviewed_frames"][1][key] = bad
                with self.assertRaisesRegex(ValueError, "role or time differs"):
                    self.check()
                self.item["reviewed_frames"][1][key] = original

    def test_original_rgb_hash_must_match_decode_receipt(self):
        self.item["rgb_sequence_sha256"] = "stale"
        with self.assertRaisesRegex(ValueError, "absent or stale"):
            self.check()


if __name__ == "__main__":
    unittest.main()
