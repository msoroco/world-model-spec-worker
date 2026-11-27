"""Controlled comparisons reject changed fixed routes and source identities."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from comparison_audit import audit, sha
from test_school_pass import scene


def make_attempt(root: Path, name: str) -> tuple[str, Path]:
    root.mkdir()
    site = scene(name)
    (root / "context.json").write_text(json.dumps(site) + "\n")
    for filename in ("original-trace.jsonl", "cameras.json"):
        (root / filename).write_text("{}\n")
    (root / "receipt.json").write_text(json.dumps({"case_id": site["case_id"]}) + "\n")
    hashes = {filename: sha(root / filename) for filename in
              ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")}
    (root / "analysis-report.json").write_text(json.dumps({
        "case_id": site["case_id"], "diagnostic_fixture": True,
        "measurements": {"source": {"sources": hashes}},
    }) + "\n")
    return site["case_id"], root


class ComparisonTests(unittest.TestCase):
    def test_session_difference_and_fixed_route_rejection(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as directory:
            root = Path(directory)
            left_id, left = make_attempt(root / "left", "active_beacon_pass")
            right_id, right = make_attempt(root / "right", "school_not_in_session")
            report = audit("school_session", left_id, left, right_id, right)
            self.assertEqual(report["declared_differences_observed"], ["school_in_session"])
            self.assertFalse(report["physical_comparison_complete"])
            site = json.loads((right / "context.json").read_text())
            site["target_route_xy"] = [[20, 1], [40, 1], [60, 1]]
            (right / "context.json").write_text(json.dumps(site) + "\n")
            hashes = {filename: sha(right / filename) for filename in
                      ("context.json", "original-trace.jsonl", "receipt.json", "cameras.json")}
            (right / "analysis-report.json").write_text(json.dumps({
                "case_id": right_id, "diagnostic_fixture": True,
                "measurements": {"source": {"sources": hashes}},
            }) + "\n")
            with self.assertRaisesRegex(ValueError, "fixed condition changed: target_route_xy"):
                audit("school_session", left_id, left, right_id, right)


if __name__ == "__main__":
    unittest.main()
