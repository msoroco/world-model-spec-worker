"""Current selected source-shape pair and fixed-condition negative probes."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "native"))
from comparison_audit import CASE_IDS, audit_pair, compare_fixed, load_original
from engineering import candidate


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def source(suffix: str, candidate_id: str = "primary") -> dict:
    attempt = (ROOT / ".runtime-work" /
               f"c10316-current-{suffix}-{candidate_id}-compat")
    return {"config": read(attempt / "config.json"),
            "native_context": {
                "native_map_sha256": "source-shaped-map",
                "initial_original_footprint": [],
                "requested_plan": candidate(suffix, candidate_id)},
            "crosswalk_context": read(attempt / "crosswalk-context.json"),
            "crossing_review": {
                "marked_highway_crosswalk_confirmed": True,
                "alley_route_connection_confirmed": True,
                "practicability_judgment": "unverified",
                "facts": {name: {"observation": "fixed source-shaped fact"}
                          for name in ("signals", "passage_space", "obstacles",
                                       "other_pedestrians")}},
            "samples": rows(attempt / "native_samples.jsonl"),
            "result": {"measured_values": {
                "observed_crosswalk_half": "right" if suffix == "reference"
                else "left"}}}


class ComparisonAuditTests(unittest.TestCase):
    def test_current_source_shape_and_nonpromotion(self):
        for candidate_id in ("primary", "fallback1", "fallback2", "fallback3"):
            reference = source("reference", candidate_id)
            contrast = source("contrast", candidate_id)
            fixed = compare_fixed(reference, contrast)
            self.assertEqual(fixed["declared_difference"],
                             "pedestrian_lateral_crosswalk_half")
            self.assertEqual(fixed["candidate_id"], candidate_id)
            self.assertAlmostEqual(fixed["observed_mean_lateral_separation_m"], 1.3)
        reference, contrast = source("reference"), source("contrast")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "reference.json", root / "contrast.json"]
            for path in paths:
                path.write_text("{}\n")
            receipts = [{"source_result_sha256": "source-shaped-result"}] * 2
            with patch("comparison_audit.load_original",
                       side_effect=[(receipts[0], reference),
                                    (receipts[1], contrast)]):
                report = audit_pair(*paths, test_shape=True)
            self.assertFalse(report["passed"])
            self.assertFalse(report["legal_verdict_claimed"])
            self.assertEqual(report["case_ids"], list(CASE_IDS))

    def test_undeclared_changes_rejected(self):
        reference, contrast = source("reference"), source("contrast")
        changed = copy.deepcopy(contrast)
        changed["config"]["duration_s"] = 11
        with self.assertRaisesRegex(ValueError, "Undeclared camera"):
            compare_fixed(reference, changed)
        changed = copy.deepcopy(contrast)
        changed["crossing_review"]["facts"]["obstacles"]["observation"] = "new obstacle"
        with self.assertRaisesRegex(ValueError, "Fixed passage"):
            compare_fixed(reference, changed)
        changed = copy.deepcopy(contrast)
        changed["native_context"]["requested_plan"]["engineering"][
            "target_lateral_m"] = 0.7
        with self.assertRaisesRegex(ValueError, "Declared 1.3 m"):
            compare_fixed(reference, changed)
        changed = copy.deepcopy(contrast)
        changed["samples"][120]["pedestrian_xy_m"][1] += 0.5
        with self.assertRaisesRegex(ValueError, "measured lateral"):
            compare_fixed(reference, changed)

    def test_unaccepted_receipt_rejected_before_source_load(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.json"
            path.write_text(json.dumps({"format": "worker-delivery-audit",
                                        "passed": False, "case_id": CASE_IDS[0],
                                        "source_shaped_unit_test": True}) + "\n")
            with self.assertRaisesRegex(ValueError, "original delivery acceptance"):
                load_original(path, CASE_IDS[0])


if __name__ == "__main__":
    unittest.main()
