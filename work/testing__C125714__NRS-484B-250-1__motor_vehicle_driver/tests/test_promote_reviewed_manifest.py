"""Synthetic protocol proof for reviewed candidate promotion."""
import hashlib
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from promote_reviewed_manifest import REQUIRED, SUFFIXES, assemble


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, sort_keys=True) + "\n", encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PromotionTests(unittest.TestCase):
    def fixture(self, base):
        cases, proof = [], {"assignment_id": ROOT.name, "cases": {}}
        for suffix in SUFFIXES:
            case_id = ROOT.name + "__" + suffix
            folder = base / suffix
            construction = folder / "construction.json"
            digest = write(construction, {"case_id": case_id, "diagnostic_only": False})
            write(folder / "measurement-contract.json", {"case_id": case_id})
            write(folder / "preflight.json", {"case_id": case_id, "passed": True, "native_started": False})
            cases.append({"case_id": case_id, "kind": "delivery", "construction": suffix + "/construction.json",
                          "construction_sha256": digest, "measurement_contract": suffix + "/measurement-contract.json",
                          "source_preflight": suffix + "/preflight.json", "candidates": []})
            proof["cases"][case_id] = {}
            for stage in REQUIRED:
                rel = suffix + "/" + stage + ".json"
                stage_hash = write(base / rel, {"case_id": case_id, "construction_sha256": digest})
                proof["cases"][case_id][stage] = {"receipt": rel, "sha256": stage_hash}
        write(base / "candidate-index.json", {"format": "worker-reviewed-delivery-candidates",
                                               "assignment_id": ROOT.name, "runtime_manifest_sha256": "a" * 64,
                                               "cases": cases})
        receipt = base / "receipt-index.json"
        write(receipt, proof)
        return receipt

    def test_promotes_only_complete_seven_case_stage_bindings(self):
        with TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            base = Path(temp)
            receipts = self.fixture(base)
            result = assemble(base, receipts, allow_scratch=True)
            self.assertEqual(result["format"], "worker-execution-manifest")
            self.assertEqual(len(result["cases"]), 7)
            for row in result["cases"]:
                self.assertEqual(row["kind"], "delivery")
                self.assertTrue(all(name in row for name in REQUIRED))
            (base / "precedence" / "construction.json").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "construction hash changed"):
                assemble(base, receipts, allow_scratch=True)

    def test_refuses_missing_receipt_and_diagnostic_construction(self):
        with TemporaryDirectory(dir=REPO / ".runtime-work") as temp:
            base = Path(temp)
            receipts = self.fixture(base)
            proof = json.loads(receipts.read_text())
            proof["cases"][ROOT.name + "__advance"].pop("compatibility")
            write(receipts, proof)
            with self.assertRaisesRegex(ValueError, "missing compatibility receipt"):
                assemble(base, receipts, allow_scratch=True)
            self.fixture(base)
            construction = base / "advance" / "construction.json"
            digest = write(construction, {"case_id": ROOT.name + "__advance", "diagnostic_only": True})
            index = json.loads((base / "candidate-index.json").read_text())
            next(row for row in index["cases"] if row["case_id"].endswith("__advance"))["construction_sha256"] = digest
            write(base / "candidate-index.json", index)
            with self.assertRaisesRegex(ValueError, "diagnostic or wrong"):
                assemble(base, receipts, allow_scratch=True)


if __name__ == "__main__":
    unittest.main()
