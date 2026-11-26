import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_queue_proposal import build
from source_audit import audit


class SourceAndQueueTests(unittest.TestCase):
    def test_immutable_source_inventory(self):
        repo = Path(__file__).resolve().parents[3]
        result = audit(repo)
        self.assertEqual(result["frozen_cell_control"], "stop_sign")
        self.assertEqual(result["accepted_metadata_count"], 2)
        self.assertEqual(result["accepted_original_file_count"], 0)
        self.assertEqual(len(result["missing_source_classes"]), 4)

    def test_exact_case_queue_order_and_command_grammar(self):
        proposal = build()
        self.assertEqual(len(proposal["cases"]), 3)
        self.assertEqual(len(proposal["comparison_audit_commands"]), 2)
        self.assertEqual([row["order"] for row in proposal["cases"]], [1, 2, 3])
        for row in proposal["cases"]:
            self.assertIn("--root \"$LOCAL_ROOT\" prepare-delivery", row["prepare_command"])
            self.assertIn("--root \"$LOCAL_ROOT\" execute-delivery", row["execute_command"])
            self.assertIn("--root \"$LOCAL_ROOT\" accept-delivery", row["accept_command"])
            self.assertIn("--review-archive /external/archive", row["accept_command"])
            self.assertIn(row["case_id"], row["postprocessing_command"])
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(json.loads((root / "gpu-queue-proposal.json").read_text()), proposal)


if __name__ == "__main__":
    unittest.main()
