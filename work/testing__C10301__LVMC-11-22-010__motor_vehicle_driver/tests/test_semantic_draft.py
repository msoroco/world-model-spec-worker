"""Current-runtime stage validation for source-preserving alley drafts."""
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
os.environ.setdefault("SCENARIO_PIPELINE_OUTPUT_ROOT", str(REPO / ".runtime-work/c10301-semantic-tests"))
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from batch_pipeline.stages import validate


class SemanticDraftTests(unittest.TestCase):
    def test_exact_stage_contracts_and_source_index(self):
        proposal = HERE / "proposals"
        read = lambda name: json.loads((proposal / (name + ".json")).read_text())
        index = read("semantic-index")
        for stage in index["stages"].values():
            for item in stage if isinstance(stage, list) else [stage]:
                path = HERE / item["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        law = "LVMC-11-22-010"
        actor = "motor_vehicle_driver"
        cell = {"cell_id": "C10301"}
        quote = read("template")["quote"]
        template = read("template")
        template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = read("judgment_observables")["observable_requirements"]
        inputs = {
            "relevance": {"request": {"cell": cell, "actor": actor},
                          "law_records": {law: {"text": quote}}},
            "template": {"request": {"law_id": law, "actor": actor},
                         "law_record": {"text": quote}},
            "judgment_observables": {"request": {"template_id": law + "@" + actor,
                                                   "phrase": "full time and attention",
                                                   "note": "Exterior motion cannot determine interior attention."}},
            "bindings": {"request": {"cell": cell, "actor": actor,
                                     "template_ids": [law + "@" + actor]}},
            "cases": {"request": {"cell": cell, "actor": actor},
                      "dependencies": [read("bindings")], "templates": [template]},
        }
        for name, context in inputs.items():
            with self.subTest(stage=name):
                validate(name, read(name), context)
        selected = {c["case_id"] for c in read("cases")["cases"]
                    if c["target_type"] != "baseline"}
        frozen = {c["case_id"] for c in json.loads((HERE / "case-plan.json").read_text())["cases"]}
        self.assertEqual(selected, frozen)

    def test_no_attention_surrogate_or_numeric_range(self):
        cases = json.loads((HERE / "proposals/cases.json").read_text())
        self.assertEqual(cases["sweep_specs"][0]["status"], "incomplete")
        self.assertTrue(cases["sweeps_expanded"])
        self.assertFalse(cases["sweep_specs"][0].get("axes"))
        for case in cases["cases"]:
            self.assertIsNone(case["variable_assignments"]["observed_attention_state"]["value"])
            self.assertIn("Exterior behavior", case["recording_description"]["limitations"][0])


if __name__ == "__main__":
    unittest.main()
