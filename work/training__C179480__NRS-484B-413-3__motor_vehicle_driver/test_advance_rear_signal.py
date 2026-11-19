"""Check the isolated comparison variable and explicit timing bounds."""

import unittest
from advance_rear_signal import TimingPlan, target


class TimingConstructionTests(unittest.TestCase):
    def test_selected_pair_differs_only_in_signal_frame_and_case_id(self):
        before = target("witness_1")
        after = target("witness_2")
        self.assertEqual(before["brake_lamp_command_frame"], 100)
        self.assertEqual(after["brake_lamp_command_frame"], 121)
        self.assertEqual(before["action_frame"], after["action_frame"])
        for key in set(before) - {"case_suffix", "brake_lamp_command_frame"}:
            self.assertEqual(before[key], after[key], key)

    def test_no_zero_or_post_action_lead(self):
        for lead in (0, 120):
            with self.assertRaises(ValueError):
                TimingPlan(signal_lead_frames=lead)

    def test_unknown_case_rejected(self):
        with self.assertRaises(ValueError):
            target("baseline")


if __name__ == "__main__":
    unittest.main()
