import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import comparison_audit
from native_construction import ASSIGNMENT


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class ProductionComparisonTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(".runtime-work")
        scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.site = {"lanes": {"source": {"lane_id": "source"},
                               "destination": {"lane_id": "destination",
                                               "centerline_world_xyz_m": [[0, 0, 0]]}},
                     "ego_blueprint": "ego", "target_vehicle_blueprint": "target",
                     "target_spawn_xyz_yaw": [0, 0, 0, 0],
                     "camera_poses_xyz_pitch_yaw": {"overview": [0, 0, 0, 0, 0]}}
        self.attempts = {}
        self.receipts = {}
        for variant in ("both_observed", "signal_missing"):
            folder = self.root / variant
            folder.mkdir()
            hashes = {}
            for name in comparison_audit.REQUIRED_SOURCES:
                path = folder / name
                path.parent.mkdir(exist_ok=True)
                path.write_text(json.dumps(self.site) if name == "reviewed-site.json" else "source\n")
                hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            config = {"duration_s": 45, "rate_hz": 20}
            (folder / "config.json").write_text(json.dumps(config))
            fixed = {"reviewed_site_sha256": hashes["reviewed-site.json"],
                     "source_lane_id": "source", "destination_lane_id": "destination",
                     "ego_blueprint": "ego", "target_vehicle_blueprint": "target",
                     "target_traffic_plan_sha256": digest({"spawn": self.site["target_spawn_xyz_yaw"],
                                                           "route": [[0, 0, 0]]}),
                     "camera_plan_sha256": digest({"poses": self.site["camera_poses_xyz_pitch_yaw"],
                                                    "sizes": comparison_audit.SIZES}),
                     "capture_duration_s": 45, "capture_rate_hz": 20}
            report = {"format": "c144550-saved-lane-change-report-v1",
                      "case_id": ASSIGNMENT + "__" + variant,
                      "original_source_hashes": hashes,
                      "legal_verdict_claimed": False,
                      "fixed_context": fixed,
                      "measurements": {"signal_precedes_center_departure": variant == "both_observed",
                                       "driver_check_observed_before_departure": True}}
            (folder / "analysis-report.json").write_text(json.dumps(report))
            self.attempts[variant] = folder
            self.receipts[variant] = self.root / (variant + "-owner.json")

    @staticmethod
    def recomputed(folder):
        return json.loads((folder / "analysis-report.json").read_text())

    @patch.object(comparison_audit, "audit_delivery")
    @patch.object(comparison_audit, "build_report")
    def test_original_attempts_bind_sources_and_comparison(self, recompute, delivery):
        delivery.return_value = {"format": "worker-delivery-audit", "passed": True}
        recompute.side_effect = self.recomputed
        result = comparison_audit.audit_original_attempts(
            "signal-prerequisite-control", self.attempts, self.receipts)
        self.assertTrue(result["production_original_attempts_audited"])
        self.assertEqual(delivery.call_count, 2)
        self.assertTrue(all(call.kwargs.get("owner_receipt") for call in delivery.call_args_list))

    @patch.object(comparison_audit, "audit_delivery")
    @patch.object(comparison_audit, "build_report")
    def test_accepted_source_original_attempt_pairs(self, recompute, delivery):
        delivery.return_value = {"format": "worker-delivery-audit", "passed": True}
        recompute.side_effect = self.recomputed
        for n, contrast in ((1, "signal_missing"), (2, "check_missing"),
                            (3, "signal_missing")):
            variant = f"accepted_source_{n}"
            folder = self.root / variant
            shutil.copytree(self.attempts["both_observed"], folder)
            report_path = folder / "analysis-report.json"
            report = json.loads(report_path.read_text())
            report["case_id"] = ASSIGNMENT + "__" + variant
            report_path.write_text(json.dumps(report))
            self.attempts[variant] = folder
            self.receipts[variant] = self.root / (variant + "-owner.json")
            if contrast == "check_missing":
                other = self.root / contrast
                shutil.copytree(self.attempts["both_observed"], other)
                report_path = other / "analysis-report.json"
                report = json.loads(report_path.read_text())
                report["case_id"] = ASSIGNMENT + "__" + contrast
                report["measurements"]["driver_check_observed_before_departure"] = False
                report_path.write_text(json.dumps(report))
                self.attempts[contrast] = other
                self.receipts[contrast] = self.root / (contrast + "-owner.json")
            cid = f"accepted-source-{n}-" + (
                "signal-control" if contrast == "signal_missing" else "check-control")
            result = comparison_audit.audit_original_attempts(
                cid, {variant: self.attempts[variant], contrast: self.attempts[contrast]},
                {variant: self.receipts[variant], contrast: self.receipts[contrast]})
            self.assertTrue(result["production_original_attempts_audited"])
            self.assertEqual(result["case_ids"][0], ASSIGNMENT + "__" + variant)

    @patch.object(comparison_audit, "audit_delivery")
    @patch.object(comparison_audit, "build_report")
    def test_missing_and_tampered_original_sources_reject(self, recompute, delivery):
        delivery.return_value = {"format": "worker-delivery-audit", "passed": True}
        recompute.side_effect = self.recomputed
        source = self.attempts["both_observed"] / "original-driver-input.jsonl"
        source.unlink()
        with self.assertRaisesRegex(ValueError, "source missing or changed"):
            comparison_audit.audit_original_attempts(
                "signal-prerequisite-control", self.attempts, self.receipts)
        source.write_text("tampered\n")
        with self.assertRaisesRegex(ValueError, "source missing or changed"):
            comparison_audit.audit_original_attempts(
                "signal-prerequisite-control", self.attempts, self.receipts)

    @patch.object(comparison_audit, "audit_delivery")
    @patch.object(comparison_audit, "build_report")
    def test_forged_measurement_rejects(self, recompute, delivery):
        delivery.return_value = {"format": "worker-delivery-audit", "passed": True}
        originals = {variant: self.recomputed(folder) for variant, folder in self.attempts.items()}
        recompute.side_effect = lambda folder: originals[folder.name]
        report_path = self.attempts["signal_missing"] / "analysis-report.json"
        forged = json.loads(report_path.read_text())
        forged["measurements"]["signal_precedes_center_departure"] = True
        report_path.write_text(json.dumps(forged))
        with self.assertRaisesRegex(ValueError, "measurement differs"):
            comparison_audit.audit_original_attempts(
                "signal-prerequisite-control", self.attempts, self.receipts)

    @patch.object(comparison_audit, "audit_delivery")
    @patch.object(comparison_audit, "build_report")
    def test_diagnostic_delivery_audit_rejects(self, recompute, delivery):
        delivery.return_value = {"format": "worker-delivery-audit-diagnostic", "passed": True}
        recompute.side_effect = self.recomputed
        with self.assertRaisesRegex(ValueError, "Native delivery audit required"):
            comparison_audit.audit_original_attempts(
                "signal-prerequisite-control", self.attempts, self.receipts)


if __name__ == "__main__":
    unittest.main()
