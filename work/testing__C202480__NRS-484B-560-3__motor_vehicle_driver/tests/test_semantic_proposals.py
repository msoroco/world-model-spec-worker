"""Pinned stage validation of C202480's source-hashed semantic drafts."""

import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]


class SemanticProposalTests(unittest.TestCase):
    def test_all_six_exact_case_drafts_and_stage_contracts(self):
        output = os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT")
        self.assertTrue(output)
        self.assertIn(ROOT / ".runtime-work", Path(output).resolve().parents)
        sys.path.insert(0, str(ROOT / "runtime"))
        from scenario_pipeline.batch_pipeline import stages
        assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
        folder = HERE / "proposals"
        index = json.loads((folder / "semantic-index.json").read_text())
        self.assertEqual(index["format"], "worker-semantic-delivery")
        self.assertEqual(index["assignment_id"], assignment["assignment_id"])
        def load(ref):
            path = HERE / ref["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), ref["sha256"])
            return json.loads(path.read_text())
        refs = index["stages"]
        request = {"cell": assignment["cell"], "actor": assignment["actor"]}
        law = assignment["law"]
        for name in ("relevance_batch", "relevance"):
            stages.validate(name, load(refs[name]),
                            {"request": request, "law_records": {law["id"]: law},
                             "dependencies": []})
        rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
        template = load(refs["template"])
        stages.validate("template", template,
                        {"request": {"law_id": law["id"], "actor": assignment["actor"]},
                         "law_record": law, "canonical_parameter_rules": rules,
                         "dependencies": []})
        for expected, ref in zip(template["structure"]["judgment_calls_needed"],
                                 refs["judgment_observables"]):
            value = load(ref)
            stages.validate("judgment_observables", value,
                            {"request": {"template_id": template["template_id"],
                                         "phrase": expected["phrase"],
                                         "note": expected["note"]},
                             "dependencies": []})
            expected["observable_requirements"] = value["observable_requirements"]
        binding = load(refs["bindings"])
        stages.validate("bindings", binding,
                        {"request": dict(request, template_ids=[template["template_id"]]),
                         "canonical_parameter_rules": rules,
                         "dependencies": [template]})
        cases = load(refs["cases"])
        stages.validate("cases", cases,
                        {"request": request, "dependencies": [binding],
                         "templates": [template], "canonical_parameter_rules": rules,
                         "judgment_completion_policy": {}})
        planned = json.loads((HERE / "case-plan.json").read_text())
        selected = {c["case_id"] for c in cases["cases"] if c["target_type"] != "baseline"}
        self.assertEqual(selected, {c["case_id"] for c in planned["cases"]})
        self.assertEqual({c["marked_highway_lane_count"] for c in planned["cases"]}, {2, 4, 5})
        self.assertEqual(len(planned["comparisons"]), 5)
        self.assertTrue(all(spec["status"] == "incomplete" for spec in cases["sweep_specs"]))


if __name__ == "__main__":
    unittest.main()
