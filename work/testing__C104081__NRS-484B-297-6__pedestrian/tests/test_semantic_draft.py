import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))


class SemanticDraftTests(unittest.TestCase):
    def test_exact_stage_chain_matches_diagnostic_constructions(self):
        from worker_exchange.semantic_delivery import validate
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
        receipt = validate(ROOT, assignment, manifest)
        self.assertEqual(receipt["selected_cases"], 5)
        self.assertEqual(receipt["stage_count"], 9)
        self.assertEqual(manifest["semantic_index_sha256"], receipt["index_sha256"])


if __name__ == "__main__":
    unittest.main()
