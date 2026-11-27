"""Check source-indication alternatives preserve controlled comparisons."""

import copy
import unittest

from branch_variants import RESPONSES, VARIANTS, check_pair, variant_request


class BranchVariants(unittest.TestCase):
    def test_four_distinct_requests(self):
        cases = [variant_request(variant, response)
                 for variant in VARIANTS for response in RESPONSES]
        self.assertEqual(len({case["case_id"] for case in cases}), 4)
        for case in cases:
            self.assertEqual((case["frames"], case["rate_hz"], case["duration_s"]),
                             (600, 20, 30))
            self.assertEqual(len(case["cameras"]), 4)
            self.assertFalse(case["physical_acceptance_claimed"])

    def test_stopped_source_hand_signal_is_a_distinct_branch(self):
        first, second = check_pair("visible_driver_hand_signal")
        self.assertIsNotNone(first["source_driver_proxy"])
        self.assertIsNone(first["officer_actor"])
        self.assertGreater(first["emergency_motion_start_frame"],
                           first["source_driver_proxy"]["signal_frames"][1])
        self.assertNotEqual(first["ego_response_policy"], second["ego_response_policy"])

    def test_officer_direction_has_source_actor(self):
        first, second = check_pair("officer_directed_otherwise")
        self.assertIsNotNone(first["officer_actor"])
        self.assertIsNone(first["source_driver_proxy"])
        self.assertNotEqual(first["ego_response_policy"], second["ego_response_policy"])

    def test_unknown_variant_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown exact"):
            variant_request("unreviewed", RESPONSES[0])

    def test_fixed_source_mutation_rejected(self):
        first, second = check_pair("visible_driver_hand_signal")
        changed = copy.deepcopy(second)
        changed["source_driver_proxy"]["spawn_xyz_m"][0] += 1
        self.assertNotEqual(first["source_driver_proxy"], changed["source_driver_proxy"])


if __name__ == "__main__":
    unittest.main()
