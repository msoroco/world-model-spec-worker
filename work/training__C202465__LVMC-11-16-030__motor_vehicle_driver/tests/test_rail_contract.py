"""Selected saved source and comparison receipt checks on the CPU."""

import hashlib
import json
from pathlib import Path
import sys
import unittest

WORK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORK))
from delivery_audit import audit


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class RailDeliveryContractTest(unittest.TestCase):
    def test_selected_saved_sources_and_comparisons(self):
        manifest = json.loads((WORK / "execution-manifest.json").read_text())
        cases = manifest["cases"]
        self.assertEqual(len(cases), 10)
        for case in cases:
            saved = case["saved_proof"]
            delivery = case["delivery_acceptance"]
            self.assertEqual(sha(saved["processing"]), saved["processing_sha256"])
            self.assertEqual(sha(WORK / delivery["test_log"]), delivery["test_log_sha256"])
            self.assertEqual(sha(WORK / delivery["negative_log"]),
                             delivery["negative_log_sha256"])
            reviewed = audit(case["case_id"], "primary", saved["attempt"],
                             saved["processing"], True)
            self.assertEqual(reviewed["case_id"], case["case_id"])
            self.assertTrue(reviewed["diagnostic_only"])
            with self.assertRaisesRegex(ValueError, "Missing source: rail-rays.jsonl"):
                audit(case["case_id"], "primary", saved["attempt"],
                      saved["processing"], True, "rail-rays.jsonl")
        comparisons = json.loads((WORK / "comparison-audit-specs.json").read_text())["comparisons"]
        self.assertEqual(len(comparisons), 9)
        for comparison in comparisons:
            receipt = WORK / comparison["receipt"]
            self.assertEqual(sha(receipt), comparison["sha256"])
            value = json.loads(receipt.read_text())
            self.assertTrue(value["diagnostic_only"])
            self.assertTrue(value["negative_rejected"])
            self.assertEqual(len(value["source_cases"]), 2)


if __name__ == "__main__":
    unittest.main()
