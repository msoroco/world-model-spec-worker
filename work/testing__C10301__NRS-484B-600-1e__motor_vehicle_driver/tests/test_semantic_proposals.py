import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("inputs/testing__C10301__NRS-484B-600-1e__motor_vehicle_driver/assignment.json")


class SemanticProposalTests(unittest.TestCase):
    def test_exact_source_quote_and_all_stage_hashes(self):
        assignment = json.loads(SOURCE.read_text())
        index = json.loads((ROOT / "proposals/semantic-index.json").read_text())
        self.assertEqual(index["assignment_id"], assignment["assignment_id"])
        self.assertEqual(index["source"]["sha256"], hashlib.sha256(SOURCE.read_bytes()).hexdigest())
        stages = index["stages"]
        self.assertEqual(set(stages), {"relevance_batch", "relevance", "template", "bindings",
                                       "cases", "judgment_observables"})
        for entry in [stages[name] for name in stages if name != "judgment_observables"] + stages["judgment_observables"]:
            path = ROOT / entry["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(entry["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        quote = assignment["law"]["text"]
        relevance = json.loads((ROOT / stages["relevance"]["path"]).read_text())
        template = json.loads((ROOT / stages["template"]["path"]).read_text())
        self.assertEqual(relevance["relevant_laws"][0]["quote"], quote)
        self.assertEqual(template["quote"], quote)
        self.assertEqual(template["structure"]["obligation"]["numeric_conditions"][0]["value"], 80)
        self.assertEqual(len(stages["judgment_observables"]), 3)

    def test_three_case_boundary_and_unresolved_judgments(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        cases = json.loads((ROOT / "proposals/cases.json").read_text())
        self.assertEqual([c["case_id"] for c in cases["cases"]],
                         [c["case_id"] for c in plan["cases"]])
        self.assertEqual([c["variable_assignments"]["requested_speed_mph"] for c in cases["cases"]],
                         [75, 80, 85])
        self.assertTrue(all(c["unresolved_judgment_calls"] for c in cases["cases"]))


if __name__ == "__main__":
    unittest.main()
