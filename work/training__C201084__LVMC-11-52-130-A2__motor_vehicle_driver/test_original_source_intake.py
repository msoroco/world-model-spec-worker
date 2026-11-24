"""Negative tests for source and manifest provenance at original intake."""

import copy
import json
import unittest
from pathlib import Path

from validate_original_source_intake import HERE, digest, review


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads((HERE / "original-source-intake.json").read_text())

    def test_pending_cases_are_not_documented(self):
        result = review(self.packet)
        self.assertTrue(result["passed"])
        self.assertFalse(result["all_original_facts_documented"])
        self.assertEqual(len(result["missing_by_case"]), 8)
        self.assertTrue(all(len(fields) == 8 for fields in result["missing_by_case"].values()))

    def test_changed_manifest_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["manifest_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            review(packet)

    def test_unbacked_documented_claim_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["cases"][0]["facts"]["fire_code_designation"]["status"] = "documented"
        with self.assertRaisesRegex(ValueError, "citation missing"):
            review(packet)

    def test_diagnostic_source_cannot_be_original_authority(self):
        packet = copy.deepcopy(self.packet)
        fact = packet["cases"][0]["facts"]["fire_code_designation"]
        path = HERE / "selected-reference-posting-pending.json"
        fact.update(status="documented", source={"path": str(path.relative_to(HERE.parents[1])),
                                                  "sha256": digest(path)}, finding="posted")
        with self.assertRaisesRegex(ValueError, "diagnostic source cannot prove original context"):
            review(packet)

    def test_claimed_acceptance_is_rejected(self):
        packet = copy.deepcopy(self.packet)
        packet["cases"][0]["legal_acceptance_claimed"] = True
        with self.assertRaisesRegex(ValueError, "claims acceptance"):
            review(packet)


if __name__ == "__main__":
    unittest.main()
