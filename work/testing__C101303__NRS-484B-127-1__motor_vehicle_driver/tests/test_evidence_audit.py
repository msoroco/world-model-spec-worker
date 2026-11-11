import importlib.util
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("evidence_audit", PACKAGE / "evidence_audit.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class EvidenceAuditTest(unittest.TestCase):
    def test_all_frozen_metadata_matches_inventory(self):
        result = MODULE.audit(ROOT, PACKAGE.name)
        evidence = json.loads((ROOT / "inputs" / PACKAGE.name / "evidence.json").read_text())
        self.assertEqual(len(result), len(evidence["recordings"]))
        self.assertEqual({r["recording_id"] for r in result},
                         {r["recording_id"] for r in evidence["recordings"]})


if __name__ == "__main__":
    unittest.main()
