"""Saved finalizer binds original trace, context, camera hashes and case identity."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_finalizer import VIEWS, finalize, sha
from school_pass import ASSIGNMENT
from test_school_pass import rows, scene


def packet(root: Path):
    context = scene()
    context_path = root / "context.json"
    context_path.write_text(json.dumps(context) + "\n")
    trace = root / "original-trace.jsonl"
    trace.write_text("\n".join(json.dumps(row) for row in rows(context)) + "\n")
    streams = {}
    for view in VIEWS:
        path = root / (view + ".mkv")
        path.write_bytes(b"test byte seal")
        streams[view] = {"path": path.name, "sha256": sha(path),
                         "fps": 20, "frame_count": 900}
    cameras = root / "cameras.json"
    cameras.write_text(json.dumps({"assignment_id": ASSIGNMENT,
                                   "case_id": context["case_id"],
                                   "fps": 20, "frame_count": 900,
                                   "streams": streams}) + "\n")
    receipt = root / "receipt.json"
    receipt.write_text(json.dumps({"assignment_id": ASSIGNMENT,
                                   "case_id": context["case_id"],
                                   "source_kind": "original_native_capture",
                                   "frame_count": 900, "fps": 20,
                                   "context_sha256": sha(context_path),
                                   "trace_sha256": sha(trace),
                                   "camera_manifest_sha256": sha(cameras)}) + "\n")
    return context["case_id"], context_path, trace, receipt, cameras


class SavedFinalizerTests(unittest.TestCase):
    def test_original_source_seal_and_missing_source_rejection(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            args = packet(root)
            with patch("saved_finalizer.inspect_video") as inspect:
                measured = finalize(*args)
            self.assertEqual(inspect.call_count, 4)
            self.assertTrue(measured["completed_pass"])
            self.assertEqual(measured["statutory_disposition"], "unresolved_pending_original_review")
            (root / "context.json").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
                finalize(*args)

    def test_original_trace_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            args = packet(root)
            (root / "original-trace.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "source seal mismatch"):
                finalize(*args)


if __name__ == "__main__":
    unittest.main()
