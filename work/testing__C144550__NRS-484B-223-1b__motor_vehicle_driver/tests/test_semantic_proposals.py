import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime" / "scenario_pipeline"))

from batch_pipeline.stages import validate


class SemanticProposalTests(unittest.TestCase):
    def test_all_canonical_stages_validate_without_legal_decision(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        proposal = ROOT / "proposals"
        load = lambda name: json.loads((proposal / name).read_text())
        law = assignment["law_id"]
        actor = assignment["actor"]
        cell = assignment["cell"]
        template_id = law + "@" + actor
        for stage in ("relevance", "relevance_batch"):
            validate(stage, load(stage + ".json"), {
                "request": {"cell": cell, "actor": actor},
                "law_records": {law: assignment["law"]}})
        validate("template", load("template.json"), {
            "request": {"law_id": law, "actor": actor},
            "law_record": assignment["law"], "canonical_parameter_rules": {}})
        judgments = []
        for number in (1, 2):
            judgment = load(f"judgment-{number}.json")
            validate("judgment_observables", judgment, {"request": {
                "template_id": template_id, "phrase": judgment["phrase"],
                "note": judgment["note"]}})
            judgments.append(judgment)
        binding = load("bindings.json")
        validate("bindings", binding, {"request": {
            "cell": cell, "actor": actor, "template_ids": [template_id]},
            "canonical_parameter_rules": {}})
        expanded_template = load("template.json")
        for row in expanded_template["structure"]["judgment_calls_needed"]:
            row["observable_requirements"] = next(
                value["observable_requirements"] for value in judgments
                if value["phrase"] == row["phrase"])
        validate("cases", load("cases.json"), {"request": {
            "cell": cell, "actor": actor}, "dependencies": [binding],
            "templates": [expanded_template]})
        self.assertEqual(len(load("cases.json")["cases"]), 3)


if __name__ == "__main__":
    unittest.main()
