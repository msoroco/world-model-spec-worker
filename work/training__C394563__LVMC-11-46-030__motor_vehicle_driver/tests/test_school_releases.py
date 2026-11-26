"""All stated release alternatives stay observation labels, not legal verdicts."""

from pathlib import Path
import sys
import unittest


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measure_school_warning import measure
from prove_school_warning import context, trace


class ReleaseVariants(unittest.TestCase):
    def test_each_observed_release_kind(self):
        variants = (("signal_device", "signal_stopped"),
                    ("signal_device", "signal_raised"),
                    ("signal_device", "signal_removed"),
                    ("flagman", "flagman_go"),
                    ("flagman", "flagman_left"),
                    ("other_person", "person_go"),
                    ("other_person", "person_left"))
        for role, event in variants:
            with self.subTest(role=role, event=event):
                measured = measure(context(), trace(role=role, release=event))
                self.assertEqual(measured["first_release_event"], event)
                self.assertEqual(measured["first_release_frame"], 250)
                self.assertFalse(measured["proceeded_before_observed_release"])
                self.assertEqual(measured["legal_compliance"], "unassessed")

    def test_no_observed_release_does_not_infer_one(self):
        measured = measure(context(), trace(release=None))
        self.assertIsNone(measured["first_release_event"])
        self.assertTrue(measured["proceeded_before_observed_release"])

    def test_role_release_mismatch_rejected(self):
        with self.assertRaisesRegex(ValueError, "role differ"):
            measure(context(), trace(role="flagman", release="signal_removed"))


if __name__ == "__main__":
    unittest.main()
