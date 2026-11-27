"""CPU fixture checks for the source-gated police comparison audit."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from police_comparison_audit import audit


class PoliceComparisonAuditTests(unittest.TestCase):
    def test_positive_pair(self):
        result = audit(ROOT)
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames_compared"], 600)
        self.assertFalse(result["original_authority_proven"])
        with self.assertRaisesRegex(ValueError, "declared source kind"):
            audit(ROOT, "original_native")

    def test_rejects_missing_source_and_wrong_axis(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as temp:
            target = Path(temp)
            for suffix in ("police_absent", "police_present"):
                case = target / "cases" / suffix
                source = target / "selected-source" / suffix
                case.mkdir(parents=True)
                source.mkdir(parents=True)
                for name in ("config.json",):
                    (case / name).write_bytes((ROOT / "cases" / suffix / name).read_bytes())
                for name in ("exception-context.json", "native_samples.jsonl"):
                    (source / name).write_bytes((ROOT / "selected-source" / suffix / name).read_bytes())
            missing = target / "selected-source/police_present/native_samples.jsonl"
            missing.unlink()
            with self.assertRaisesRegex(ValueError, "Missing comparison source"):
                audit(target)
            missing.write_bytes((ROOT / "selected-source/police_present/native_samples.jsonl").read_bytes())
            context_path = target / "selected-source/police_present/exception-context.json"
            context = json.loads(context_path.read_text())
            context["exception_request"] = None
            context_path.write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "axis did not change"):
                audit(target)


if __name__ == "__main__":
    unittest.main()
