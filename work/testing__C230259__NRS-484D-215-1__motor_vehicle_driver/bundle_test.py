"""Bundled exact-case offline test; no Native server is contacted."""
import os
import unittest
from unittest.mock import patch

import runner


class SelectedBeamBundleTests(unittest.TestCase):
    def test_exact_selected_case_and_profile(self):
        config = runner.check()
        self.assertTrue(config["selected_case_id"].startswith(runner.ASSIGNMENT + "__"))
        self.assertEqual(config["frame_count"], 900)

    def test_capture_refuses_missing_reviewed_site_packet(self):
        with patch.dict(os.environ, {"BEAM_ROAD_SITE_PACKET": ""}), \
             patch("sys.argv", ["runner.py", "--output-dir", "unused-attempt"]):
            with self.assertRaisesRegex(ValueError, "BEAM_ROAD_SITE_PACKET"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
