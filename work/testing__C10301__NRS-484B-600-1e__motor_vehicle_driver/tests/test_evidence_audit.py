import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
spec = importlib.util.spec_from_file_location("evidence_audit", ROOT / "evidence_audit.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AuditTests(unittest.TestCase):
    def test_all_three_frozen_records_verified_without_reuse_claim(self):
        result = module.audit(REPO, ROOT.name)
        self.assertEqual(len(result["records"]), 3)
        self.assertTrue(all(row["frames"] == 900 for row in result["records"]))
        self.assertIn("pending", result["reuse_decision"])


if __name__ == "__main__":
    unittest.main()
