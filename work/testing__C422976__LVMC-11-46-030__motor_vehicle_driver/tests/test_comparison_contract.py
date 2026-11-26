"""Selected comparison declarations isolate the intended controller facts."""

import unittest

from comparison_audit import EXPECTED, audit, definitions


class ComparisonContractTests(unittest.TestCase):
    def test_declared_differences(self):
        cases, comparisons = definitions()
        self.assertEqual(len(comparisons), 12)
        for cid, comparison in comparisons.items():
            left, right = [cases[case_id] for case_id in comparison["case_ids"]]
            one = {name: item["value"] for name, item in left["variable_assignments"].items()}
            two = {name: item["value"] for name, item in right["variable_assignments"].items()}
            changed = {name for name in one if one[name] != two[name]}
            expected = EXPECTED[cid] if cid in EXPECTED else set(comparison["deliberate_differences"])
            self.assertEqual(changed, expected, cid)

    def test_all_twelve_source_bound_comparison_protocols(self):
        _, comparisons = definitions()
        for index, (comparison_id, pair) in enumerate(comparisons.items()):
            receipts = []
            for side, case_id in enumerate(pair["case_ids"]):
                receipts.append({"format": "c422976-original-delivery-audit-v1",
                                 "case_id": case_id, "source_kind": "original_native_attempt",
                                 "frames_checked": 900,
                                 "physical_completion": "requires independent local review",
                                 "attempt_id": "synthetic-%d-%d" % (index, side),
                                 "trace_sha256": "synthetic-trace-%d-%d" % (index, side),
                                 "site_sha256": "synthetic-site-same",
                                 "measurement": {"stop": {"first_zero_speed_frame": 200 + side},
                                                 "warning": {"source_bound": True},
                                                 "release": {"source_bound": True}}})
            result = audit(comparison_id, *receipts)
            self.assertEqual(result["comparison_id"], comparison_id)
            self.assertFalse(result["physical_acceptance"])
            changed_site = dict(receipts[1], site_sha256="synthetic-site-changed")
            with self.assertRaisesRegex(ValueError, "site changed"):
                audit(comparison_id, receipts[0], changed_site)
            missing_warning = dict(receipts[1], measurement={
                "stop": {"first_zero_speed_frame": 201},
                "warning": {"source_bound": False},
                "release": {"source_bound": True}})
            with self.assertRaisesRegex(ValueError, "source-bound"):
                audit(comparison_id, receipts[0], missing_warning)


if __name__ == "__main__":
    unittest.main()
