"""Draft semantic stages preserve the exact law and six unresolved cases."""
import hashlib
import json
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from build_semantic_proposals import ACTOR, ASSIGNMENT, LAW, PHRASE, build


class SemanticProposalTests(unittest.TestCase):
    def test_canonical_stage_files_and_exact_case_coverage(self):
        stages = build()
        index = json.loads((ROOT / "proposals" / "semantic-index.json").read_text())
        self.assertEqual(index["assignment_id"], ASSIGNMENT)
        self.assertEqual(index["stages"], stages)
        entries = [item for value in stages.values() for item in
                   (value if isinstance(value, list) else [value])]
        for item in entries:
            path = ROOT / item["path"]
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), item["sha256"])
        plan = json.loads((ROOT / "case-plan.json").read_text())
        template = json.loads((ROOT / "proposals" / "template.json").read_text())
        self.assertEqual(template["quote"], plan["law_text"])
        self.assertEqual(template["actor"], ACTOR)
        self.assertIn("Except as otherwise provided in this Chapter",
                      template["structure"]["exceptions"][0]["source_clause"])
        self.assertEqual(template["structure"]["obligation"]["numeric_conditions"], [])
        proposal = json.loads((ROOT / "proposals" / "cases.json").read_text())
        planned_ids = {case["case_id"] for case in plan["cases"]}
        proposed_ids = {case["case_id"] for case in proposal["cases"] if case["target_law_id"]}
        self.assertEqual(planned_ids, proposed_ids)
        self.assertTrue(all(case["target_type"] == "boundary_probe" for case in
                            proposal["cases"] if case["target_law_id"]))
        self.assertTrue(all(PHRASE in case["unresolved_judgment_calls"] for case in proposal["cases"]))
        self.assertEqual(proposal["sweep_specs"][0]["status"], "incomplete")
        self.assertEqual(proposal["sweep_specs"][0]["target_law_id"], LAW)


if __name__ == "__main__":
    unittest.main()
