"""Saved measurement tests using bounded synthetic source files."""

import json
import os
from pathlib import Path
import tempfile
import unittest

from analysis import build_report
from native_adapter import NativeAdapter
from package_contract import ASSIGNMENT


HERE = Path(__file__).resolve().parents[1]


class SavedAnalysisTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        self.temp = tempfile.TemporaryDirectory(dir=scratch, prefix="c380107-analysis-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case = ASSIGNMENT + "__core_no_hov"
        spec = json.loads((HERE / "cases/core_no_hov/diagnostic-spec.json").read_text())
        for name in ("context.json", "trace.json"):
            (self.root / name).write_text(spec["files"][name])

    def test_synthetic_case_source_measured_but_unresolved(self):
        report = build_report(self.root, self.case)
        self.assertEqual(len(report["measurements"]), 6)
        self.assertFalse(report["legal_verdict_claimed"])
        self.assertEqual(report["measurements"]["hov_qualification_observation"]["value"]["hov_legal_exception_judgment"], "unresolved")

    def test_missing_case_context_rejected(self):
        (self.root / "context.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: context.json"):
            build_report(self.root, self.case)

    def test_diagnostic_cannot_be_relabelled_original(self):
        context = json.loads((self.root / "context.json").read_text())
        context["diagnostic_fixture"] = False
        (self.root / "context.json").write_text(json.dumps(context) + "\n")
        with self.assertRaisesRegex(ValueError, "original-receipt.json"):
            build_report(self.root, self.case)

    def test_original_capture_receipt_binds_jsonl_and_wrapper(self):
        adapter = NativeAdapter.__new__(NativeAdapter)
        adapter.output_dir = self.root
        adapter.owned = []
        adapter.world = None
        adapter.previous_settings = None
        source_names = ("lane_geometry", "posted_limit", "geographical_boundary", "actor_poses",
                        "hov_designation", "hov_hours", "hov_occupancy_rule", "hov_access",
                        "hov_sign", "hov_vehicle_category", "hov_compliance",
                        "knowledge_circumstances", "other_exceptions")
        refs = {name: {"path": name + ".json", "sha256": "a" * 64} for name in source_names}
        adapter.scene = {"case_id": self.case, "site_path": "reviewed-site.json",
                         "site_sha256": "b" * 64, "source_refs": refs,
                         "same_direction_lane_ids": ["L0", "L1"], "extreme_left_lane_id": "L0",
                         "posted_limit_mps": 10.0,
                         "schedule": {"hov_designation_request": "none",
                                      "hov_compliance_request": "unresolved"},
                         "actor_poses": {"reviewed_original_occupant_count": 2}}
        adapter.rows = [{"frame": i, "time_s": i / 20, "ego_lane_id": "L0",
                         "rear_lane_id": "L0", "ego_speed_mps": 7.0,
                         "rear_speed_mps": 9.0, "rear_to_ego_signed_gap_m": 20 - i / 10,
                         "sign_present_readback": i >= 120} for i in range(900)]
        adapter.frame_map = [{"frame": i} for i in range(900)]
        adapter.close()
        report = build_report(self.root, self.case)
        self.assertFalse(report["diagnostic_fixture"])
        self.assertEqual(report["measurements"]["hov_qualification_observation"]["value"]["occupancy_count"], 2)
        with (self.root / "original-motion.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "original source bytes changed"):
            build_report(self.root, self.case)


if __name__ == "__main__":
    unittest.main()
