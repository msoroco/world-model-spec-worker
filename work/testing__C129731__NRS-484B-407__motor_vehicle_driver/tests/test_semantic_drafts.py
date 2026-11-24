import json
import hashlib
import sys
import unittest
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime" / "scenario_pipeline"))
from batch_pipeline import stages


class SemanticDraftTests(unittest.TestCase):
    def setUp(self):
        self.assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
        self.law_id = self.assignment["law_id"]
        self.law = self.assignment["law"]
        self.request = {"cell": self.assignment["cell"], "actor": self.assignment["actor"]}
        self.rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())

    def read(self, name):
        return json.loads((HERE / "proposals" / (name + ".json")).read_text())

    def test_six_source_bound_draft_stages_validate(self):
        relevance = self.read("relevance")
        self.assertEqual(relevance, self.read("relevance_batch"))
        for stage in ("relevance", "relevance_batch"):
            stages.validate(stage, deepcopy(relevance),
                            {"request": self.request, "law_records": {self.law_id: self.law}})
        template = self.read("template")
        stages.validate("template", deepcopy(template),
                        {"request": {"law_id": self.law_id, "actor": self.assignment["actor"]},
                         "law_record": self.law, "canonical_parameter_rules": self.rules})
        judgment = self.read("judgment-1")
        phrase = template["structure"]["judgment_calls_needed"][0]
        stages.validate("judgment_observables", deepcopy(judgment),
                        {"request": {"template_id": template["template_id"], **phrase}})
        binding = self.read("bindings")
        stages.validate("bindings", deepcopy(binding),
                        {"request": dict(self.request, template_ids=[template["template_id"]]),
                         "canonical_parameter_rules": self.rules,
                         "dependencies": [template]})
        self.assertEqual(binding["law_refs"][0]["template_id"], template["template_id"])
        template["structure"]["judgment_calls_needed"][0]["observable_requirements"] = \
            judgment["observable_requirements"]
        cases = self.read("cases")
        stages.validate("cases", deepcopy(cases),
                        {"request": self.request, "dependencies": [binding],
                         "templates": [template], "canonical_parameter_rules": self.rules,
                         "judgment_completion_policy": {}})
        self.assertEqual(len(cases["cases"]), 4)
        self.assertEqual(cases["sweep_specs"][0]["status"], "incomplete")
        self.assertEqual([c["probe"]["test_value"] for c in cases["cases"][1:]],
                         [499, 500, 501])
        index = self.read("semantic-index")
        self.assertEqual(index["format"], "worker-semantic-delivery")
        self.assertEqual(set(index["stages"]), {"relevance_batch", "relevance",
                                                "template", "judgment_observables",
                                                "bindings", "cases"})
        for ref in list(index["stages"].values()):
            for item in ref if isinstance(ref, list) else [ref]:
                path = HERE / item["path"]
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                                 item["sha256"])

    def test_exact_quote_and_numeric_contract_reject_stale_source(self):
        template = self.read("template")
        template["quote"] = "anticipated legal outcome"
        with self.assertRaisesRegex(ValueError, "Template quote is not exact"):
            stages.validate("template", template,
                            {"request": {"law_id": self.law_id,
                                         "actor": self.assignment["actor"]},
                             "law_record": self.law,
                             "canonical_parameter_rules": self.rules})
        template = self.read("template")
        del template["structure"]["activation"]["numeric_conditions"][0]["unit"]
        with self.assertRaisesRegex(ValueError, "Numeric condition requires"):
            stages.validate("template", template,
                            {"request": {"law_id": self.law_id,
                                         "actor": self.assignment["actor"]},
                             "law_record": self.law,
                             "canonical_parameter_rules": self.rules})
