"""Check returned diagnostic proof inventory without promoting it to delivery."""
import json
from pathlib import Path
import sys
import unittest


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from statutory_comparison_audit import audit as compare
from build_source_gated_manifest import build as select_production
from native_attempt import verify_review_sources
import tempfile


class AllDiagnosticCpuTests(unittest.TestCase):
    def test_all_accepted_cases_have_distinct_diagnostic_constructions_and_contracts(self):
        manifest = json.loads((HERE / "execution-manifest.diagnostic.json").read_text())
        matrix = json.loads((HERE / "statutory-matrix.draft.json").read_text())
        plan = json.loads((HERE / "case-plan.json").read_text())
        self.assertEqual({entry["case_id"] for entry in manifest["cases"]},
                         set(matrix["accepted_recordings"]))
        self.assertTrue(all(row["status"] == "selected_required"
                            for row in plan["requirement_dispositions"]))
        self.assertEqual(len(manifest["cases"]), 11)
        for entry in manifest["cases"]:
            with self.subTest(case=entry["case_id"]):
                construction = json.loads((HERE / entry["construction"]).read_text())
                contract = json.loads((HERE / entry["measurement_contract"]).read_text())
                fixture = json.loads((HERE / Path(entry["fixture_recipe"]).name).read_text())
                self.assertTrue(construction["diagnostic_only"])
                self.assertEqual(construction["case_id"], contract["case_id"])
                self.assertEqual(contract["case_id"], entry["case_id"])
                self.assertEqual(fixture["format"], "worker-fixture-recipe")
                indices = {row["disposition_index"] for row in contract["requirements"]}
                expected = {index for index, row in enumerate(plan["requirement_dispositions"])
                            if entry["case_id"] in row["case_ids"]}
                self.assertEqual(indices, expected)

    def test_original_comparison_rejects_unreviewed_expectations(self):
        plan = json.loads((HERE / "case-plan.json").read_text())
        stages = {case["case_id"]: Path("/nonexistent") for case in plan["cases"]}
        with self.assertRaisesRegex(ValueError, "independent original-source expectations"):
            compare(stages, diagnostic_fixture=False)
        with self.assertRaisesRegex(ValueError, "every exact accepted case"):
            compare({}, diagnostic_fixture=True)

    def test_diagnostic_bundle_cannot_become_original_production_selection(self):
        manifest = json.loads((HERE / "execution-manifest.diagnostic.json").read_text())
        cases = {entry["case_id"]: {"reviewed_site": "diagnostic-site.json"}
                 for entry in manifest["cases"]}
        with tempfile.TemporaryDirectory() as directory:
            assembly = Path(directory) / "assembly.json"
            assembly.write_text(json.dumps({"assignment_id": HERE.name, "cases": cases}) + "\n")
            with self.assertRaisesRegex(ValueError, "source-grounded sweeps"):
                select_production(assembly)
            construction = json.loads((HERE / "construction-marked_stop_line_response.json").read_text())
            site_text = next(row["content"] for row in construction["files"]
                             if row["path"] == "diagnostic-site.json")
            site_path = Path(directory) / "diagnostic-site.json"
            site_path.write_text(site_text)
            with self.assertRaises((ValueError, KeyError, TypeError)):
                verify_review_sources(json.loads(site_text), site_path,
                                      diagnostic_fixture=False)
        self.assertFalse((HERE / "execution-manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
