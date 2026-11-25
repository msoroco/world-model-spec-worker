"""Exact stand bundle and unsourced launch checks."""
import json
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import runner
from stand import SourceError
from stand_converter_source import audit as audit_converter_sources


class BundleTests(unittest.TestCase):
    def test_exact_source_gated_case(self):
        config, case = runner.check()
        self.assertEqual(case["case_id"], config["selected_case_id"])

    def test_original_records_required(self):
        with self.assertRaisesRegex(SourceError, "reviewed original stand"):
            runner.run(None, None, None, None)

    def test_missing_converter_packet_rejected(self):
        root = Path(__file__).resolve().parents[1]
        with self.assertRaisesRegex(SourceError, "missing original converter source"):
            audit_converter_sources(root, {"case_id": "source-gated", "first_frame": 1})

    def test_native_run_requires_runtime_materialized_attempt(self):
        scratch = Path(__file__).resolve().parents[3] / ".runtime-work"
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c135087-runner-") as temporary:
            root = Path(temporary)
            refs = []
            for name in ("site", "vehicle"):
                source = root / (name + ".json")
                source.write_text(json.dumps({"format": "original_source_test_shape"}))
                refs.append({"path": str(source),
                             "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
            with patch.object(runner.importlib, "import_module",
                              return_value=SimpleNamespace(open_session=object())):
                with self.assertRaisesRegex(SourceError, "materialized by runtime.py capture"):
                    runner.run(*refs, "native_test_adapter", root / "unmaterialized")


if __name__ == "__main__":
    unittest.main()
