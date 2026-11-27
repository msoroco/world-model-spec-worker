"""Saved-only diagnostic analysis returns source-bound measurements and rejects omissions."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from analysis import analyze, sha
from test_school_pass import rows, scene


class AnalysisTests(unittest.TestCase):
    def test_diagnostic_selected_measurements_and_missing_context(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            bundle = Path(__file__).resolve().parents[1]
            for name in ("config.json", "construction.json"):
                shutil.copyfile(bundle / name, root / name)
            selected = json.loads((bundle / "config.json").read_text())["selected_case_id"]
            site = scene(selected.rsplit("__", 1)[1])
            (root / "context.json").write_text(json.dumps(site) + "\n")
            original = rows(site)[:9]
            (root / "original-trace.jsonl").write_text("\n".join(json.dumps(row) for row in original) + "\n")
            (root / "trace.jsonl").write_text("\n".join(json.dumps({"frame": row["original_frame"],
                                                                       "time_s": row["time_s"]})
                                                     for row in original) + "\n")
            (root / "cameras.json").write_text(json.dumps({"case_id": site["case_id"]}) + "\n")
            (root / "fixture-provenance.json").write_text(json.dumps({"diagnostic_fixture": True,
                                                                         "frames": 9}) + "\n")
            (root / "receipt.json").write_text(json.dumps({
                "assignment_id": site["case_id"].rsplit("__", 1)[0],
                "case_id": site["case_id"], "source_kind": "synthetic_diagnostic_fixture",
                "context_sha256": sha(root / "context.json"),
                "trace_sha256": sha(root / "original-trace.jsonl"),
                "camera_manifest_sha256": sha(root / "cameras.json"),
            }) + "\n")
            report = analyze(root, root / "analysis-report.json")
            self.assertEqual(len(report["measurements"]), 5)
            self.assertTrue(report["diagnostic_fixture"])
            self.assertFalse(json.loads((root / "result.json").read_text())["physical_acceptance_claimed"])
            (root / "context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
                analyze(root, root / "analysis-report-2.json")


if __name__ == "__main__":
    unittest.main()
