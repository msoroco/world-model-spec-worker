"""Check that every selected exact case has a physical delivery entry."""
import json
import unittest
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]


class ManifestConsistencyTests(unittest.TestCase):
    def test_selected_cases_have_one_delivery_entry_each(self):
        plan = json.loads((PACKAGE / "case-plan.json").read_text())
        manifest = json.loads((PACKAGE / "execution-manifest.json").read_text())
        planned = {case["case_id"] for case in plan["cases"]}
        delivered = [case["case_id"] for case in manifest["cases"]]
        self.assertEqual(len(delivered), len(set(delivered)))
        self.assertEqual(planned, set(delivered))
        self.assertEqual(8, len(planned))
