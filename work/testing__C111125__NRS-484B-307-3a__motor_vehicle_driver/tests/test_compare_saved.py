"""Focused source custody checks for production saved comparisons."""
import json
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compare_saved import native_custody, sha


class NativeCustodyTests(unittest.TestCase):
    def test_sealed_native_source_accepted_then_changed_source_rejected(self):
        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            original = attempt / "original-events.json"
            original.write_text("[]\n")
            (attempt / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "native", "diagnostic_fixture": False}) + "\n")
            seal = {"format": "worker-sealed-capture", "provenance_kind": "native",
                    "diagnostic_fixture": False, "frames": 900,
                    "events": ["capture_finished", "encoders_closed", "restoration_verified"],
                    "restoration": {"restored": True},
                    "sources": {"original-events.json": sha(original)}}
            path = attempt / "capture-seal.json"
            path.write_text(json.dumps(seal) + "\n")
            self.assertEqual(native_custody(attempt), sha(path))
            original.write_text("[{}]\n")
            with self.assertRaisesRegex(ValueError, "sealed original source differs"):
                native_custody(attempt)

    def test_synthetic_provenance_rejected_in_native_mode(self):
        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            attempt = Path(temporary)
            (attempt / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
            with self.assertRaisesRegex(ValueError, "original Native acquisition provenance"):
                native_custody(attempt)
