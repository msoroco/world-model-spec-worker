"""Canonical stage and diagnostic construction stay tied to the exact selection."""
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
from worker_exchange import semantic_delivery


class SemanticDraftTests(unittest.TestCase):
    def test_exact_stage_chain_and_selected_recording(self):
        assignment = json.loads((REPO / "inputs" / HERE.name / "assignment.json").read_text())
        manifest = json.loads((HERE / "execution-manifest.draft.json").read_text())
        result = semantic_delivery.validate(HERE, assignment, manifest)
        self.assertEqual(result["selected_cases"], 9)
        self.assertEqual(result["stage_count"], 10)

    def test_no_diagnostic_legal_outcome(self):
        cases = json.loads((HERE / "proposals/cases.json").read_text())["cases"]
        selected = [case for case in cases if case["target_type"] != "baseline"]
        self.assertEqual(len(selected), 9)
        self.assertEqual({case["target_type"] for case in selected}, {"boundary_probe"})
        self.assertTrue(all(len(case["unresolved_judgment_calls"]) == 5 for case in selected))


if __name__ == "__main__":
    unittest.main()
