"""Selected comparison declarations isolate the intended controller facts."""

import unittest

from comparison_audit import EXPECTED, definitions


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


if __name__ == "__main__":
    unittest.main()
