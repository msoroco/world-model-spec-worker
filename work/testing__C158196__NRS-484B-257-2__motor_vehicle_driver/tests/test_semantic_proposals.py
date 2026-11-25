"""Run the pinned semantic stage validators on this assignment's draft chain."""
import copy
import hashlib
import json
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
OUTPUT = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "")
if ".runtime-work" not in Path(OUTPUT).parts:
    raise RuntimeError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work before runtime import")
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from batch_pipeline import stages


class SemanticProposalTest(unittest.TestCase):
    def test_all_stages_and_source_hashes(self):
        assignment = json.loads((REPO / "inputs" / FOLDER.name / "assignment.json").read_text())
        proposal = FOLDER / "proposals"
        index = json.loads((proposal / "semantic-index.json").read_text())
        self.assertEqual(index["assignment_id"], assignment["assignment_id"])
        def load(ref):
            path = REPO / "work" / FOLDER.name / ref["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), ref["sha256"])
            return json.loads(path.read_text())
        refs = index["stages"]
        common = {"request": {"cell": assignment["cell"], "actor": assignment["actor"]},
                  "law_records": {assignment["law_id"]: assignment["law"]}, "dependencies": []}
        for stage in ("relevance_batch", "relevance"):
            stages.validate(stage, load(refs[stage]), common)
        rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
        template = load(refs["template"])
        stages.validate("template", template, {"request": {"law_id": assignment["law_id"],
                        "actor": assignment["actor"]}, "law_record": assignment["law"],
                        "canonical_parameter_rules": rules, "dependencies": []})
        enriched = copy.deepcopy(template)
        for item, ref in zip(enriched["structure"]["judgment_calls_needed"], refs["judgment_observables"]):
            judgment = load(ref)
            stages.validate("judgment_observables", judgment, {
                "request": {"template_id": template["template_id"], "phrase": item["phrase"],
                            "note": item["note"]}, "dependencies": []})
            item["observable_requirements"] = judgment["observable_requirements"]
        binding = load(refs["bindings"])
        stages.validate("bindings", binding, {"request": {"cell": assignment["cell"],
                        "actor": assignment["actor"], "template_ids": [template["template_id"]]},
                        "canonical_parameter_rules": rules, "dependencies": [enriched]})
        stages.validate("cases", load(refs["cases"]), {
            "request": common["request"], "dependencies": [binding], "templates": [enriched],
            "canonical_parameter_rules": rules, "judgment_completion_policy": {}})


if __name__ == "__main__":
    unittest.main()
