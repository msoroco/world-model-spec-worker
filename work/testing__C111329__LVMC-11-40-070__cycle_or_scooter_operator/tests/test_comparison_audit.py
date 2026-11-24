import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from comparison_audit import audit, audit_from_sources
from test_saved_instruction import CASE, SITE, packet


class TestComparisonAudit(unittest.TestCase):
    def test_source_bound_motion_pair_and_rejections(self):
        scratch = REPO / ".runtime-work/c111329-comparison/tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            site = {**SITE, "map_name": "source-reviewed-map",
                    "jurisdiction_source": "reviewed-jurisdiction",
                    "governed_approach": "eastbound",
                    "camera_contract": "four-original-cameras",
                    "device_authority_source": "reviewed-device-authority",
                    "vehicle_applicability_source": "reviewed-vehicle-applicability"}
            site_path = root / "site.json"
            site_path.write_text(json.dumps(site) + "\n")
            site_sha = hashlib.sha256(site_path.read_bytes()).hexdigest()
            hold = {**CASE, "case_id": "red-hold", "operator_motion": "hold_before_stop_line",
                    "device_type": "signal"}
            cross = {**CASE, "case_id": "red-cross", "device_type": "signal"}
            cases = {row["case_id"]: row for row in (hold, cross)}
            sources = {}
            for case in (hold, cross):
                data = packet(case)
                data["site_sha256"] = site_sha
                path = root / (case["case_id"] + ".json")
                path.write_text(json.dumps(data) + "\n")
                sources[case["case_id"]] = (path, hashlib.sha256(path.read_bytes()).hexdigest())
            comparison = {"comparison_id": "red_operator_motion",
                          "case_ids": ["red-hold", "red-cross"],
                          "deliberate_variable": "operator_motion"}
            receipt = audit_from_sources(comparison, cases, site_path, site_sha, sources)
            self.assertTrue(receipt["passed"])
            self.assertEqual(receipt["legal_assessment"], "unresolved")
            with self.assertRaisesRegex(ValueError, "site source hash mismatch"):
                audit_from_sources(comparison, cases, site_path, "0" * 64, sources)
            broken = dict(sources)
            broken["red-cross"] = (sources["red-cross"][0], "0" * 64)
            with self.assertRaisesRegex(ValueError, "trace hash mismatch"):
                audit_from_sources(comparison, cases, site_path, site_sha, broken)
            same = {**comparison, "case_ids": ["red-hold", "red-hold"]}
            with self.assertRaisesRegex(ValueError, "declared variable did not differ"):
                audit_from_sources(same, cases, site_path, site_sha, sources)

    def test_fixed_context_and_missing_source_rejected(self):
        base = {"format": "c111329-saved-instruction-measurement",
                "source_kind": "original_native", "legal_assessment": "unresolved",
                "bike_id": "22", "device_id": "10", "crossing_frame": None,
                "hold_window_frames": [980, 999], "device_state_at_response": "red",
                "officer_command_at_response": "none",
                "source_hashes": {"site": "a" * 64, "trace": "b" * 64},
                "context": {"map_name": "same-map", "duration_s": 45}}
        left = {**base, "case_id": "hold"}
        right = {**base, "case_id": "cross", "crossing_frame": 550,
                 "hold_window_frames": None}
        comparison = {"comparison_id": "motion", "case_ids": ["hold", "cross"],
                      "deliberate_variable": "operator_motion"}
        self.assertTrue(audit(comparison, left, right)["passed"])
        with self.assertRaisesRegex(ValueError, "fixed condition changed"):
            audit(comparison, left, {**right, "context": {"map_name": "different-map"}})
        with self.assertRaisesRegex(ValueError, "missing source-bound context"):
            audit(comparison, left, {**right, "source_hashes": {"site": "a" * 64}})
        with self.assertRaisesRegex(ValueError, "ambiguous original movement"):
            audit(comparison, left, {**right, "hold_window_frames": [980, 999]})
