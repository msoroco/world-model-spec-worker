"""Conditional semantic activation is tied to the reviewed source preflight."""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from activate_reviewed_semantic import activate
from reviewed_delivery_author import author
from test_reviewed_delivery_author import fixture


class ActivateReviewedSemanticTest(unittest.TestCase):
    def test_source_bound_positive_and_changed_receipt_negative(self):
        assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
        with TemporaryDirectory(dir=REPO / ".runtime-work") as source, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as candidate, \
             TemporaryDirectory(dir=REPO / ".runtime-work") as preflight:
            fixture(source)
            output = Path(candidate) / "candidate"
            receipts = Path(preflight) / "preflight"
            author(source, ROOT / "candidate-map.xodr", output, receipts, scratch_output=True)
            result = activate(output, assignment)
            self.assertEqual(result["selected_cases"], 7)
            self.assertEqual(result["stage_count"], 7)
            index = json.loads((output / "proposals/semantic-index.json").read_text())
            self.assertEqual(index["assignment_id"], ROOT.name)
            receipt = receipts / "precedence/preflight.json"
            content = json.loads(receipt.read_text())
            content["map_sha256"] = "0" * 64
            receipt.write_text(json.dumps(content))
            with self.assertRaisesRegex(ValueError, "does not bind original packet and map"):
                activate(output, assignment)


if __name__ == "__main__":
    unittest.main()
