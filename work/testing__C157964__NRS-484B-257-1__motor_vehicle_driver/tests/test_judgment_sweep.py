"""Diagnostic CPU structure probes; mocked custody is never original evidence."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from judgment_sweep import audit_sweep, region
from yield_view import CASES


class SweepTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plan = json.loads((ROOT / "judgment-probe-plan.json").read_text())
        self.claims = []
        for spec in self.plan["ranges"]:
            for name in ("below", "inside", "above"):
                if spec["planning_targets"][name] is None:
                    continue
                attempt = self.root / f"{spec['range_index']}-{name}"
                attempt.mkdir()
                (attempt / "measurement.json").write_text(json.dumps({
                    "minimum_original_approach_speed_mps":
                        {"below": -1, "inside": .004, "above": .2}[name],
                    "through_center_station_at_all_reference_m":
                        {"below": -10, "inside": 20, "above": 50}[name],
                }) + "\n")
                self.claims.append({"range_index": spec["range_index"],
                                    "region": name, "attempt": str(attempt),
                                    "case_id": ROOT.name + "__" + CASES[0].case_id,
                                    "expected_site_packet_sha256": "source-hash"})

    def _audit(self, source_kind=False):
        with patch("judgment_sweep.audit_saved", return_value={
                "diagnostic_fixture": source_kind,
                "native_seal_sha256": "mocked-only"}):
            return audit_sweep(self.plan, self.claims, REPO,
                               trusted_site_hashes={ROOT.name + "__" + CASES[0].case_id:
                                                    "source-hash"})

    def test_all_four_source_ranges_and_endpoint(self):
        report = self._audit()
        self.assertEqual(len(report["ranges"]), 4)
        self.assertEqual([len(item["witnesses"]) for item in report["ranges"]],
                         [2, 3, 2, 3])
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertIsNone(report["legal_judgment"])

    def test_missing_region_and_diagnostic_rejected(self):
        missing = self.claims.pop()
        with self.assertRaisesRegex(ValueError, "sweep region missing"):
            self._audit()
        self.claims.append(missing)
        with self.assertRaisesRegex(ValueError, "diagnostic sweep"):
            self._audit(source_kind=True)

    def test_wrong_value_and_source_hash_rejected(self):
        self.claims.append(dict(self.claims[0], region="below"))
        with self.assertRaisesRegex(ValueError, "impossible nonnegative below"):
            self._audit()
        self.claims.pop()
        self.plan["ranges"][0]["source_ref"]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "frozen judgment range source changed"):
            self._audit()

    def test_region_has_no_legal_cutoff(self):
        self.assertEqual(region(0, 0, 1), "inside")
        self.assertEqual(region(1, 0, 1), "inside")
        self.assertEqual(region(-.1, 0, 1), "below")
        self.assertEqual(region(1.1, 0, 1), "above")

    def test_independent_site_hash_required(self):
        with patch("judgment_sweep.audit_saved", return_value={
                "diagnostic_fixture": False,
                "native_seal_sha256": "mocked-only"}):
            with self.assertRaisesRegex(ValueError, "independently reviewed site hash differs"):
                audit_sweep(self.plan, self.claims, REPO,
                            trusted_site_hashes={ROOT.name + "__" + CASES[0].case_id:
                                                 "wrong-hash"})


if __name__ == "__main__":
    unittest.main()
