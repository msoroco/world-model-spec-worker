"""Portable exact railway bundle checks for runtime offline materialization."""
import unittest

import runner


class OfflineRailCase(unittest.TestCase):
    def test_exact_case_profile(self):
        scene = runner.load_case()
        self.assertEqual(scene["case_id"], scene["assignment_id"] + "__" + scene["case_key"])
        self.assertEqual(scene["duration_frames"], 900)
        self.assertEqual(scene["rate_hz"], 20)

    def test_native_sources_are_required(self):
        with self.assertRaisesRegex(ValueError, "source-hashed reviewed railway site packet required"):
            runner._reviewed_file(None, None, "site packet")
        with self.assertRaisesRegex(ValueError, "source-hashed reviewed railway operator module required"):
            runner._reviewed_file(None, None, "operator module")


if __name__ == "__main__":
    unittest.main()
