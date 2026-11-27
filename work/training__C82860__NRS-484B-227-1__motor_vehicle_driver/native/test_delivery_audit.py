"""Independent saved source audit and rejection probes."""

import json
from pathlib import Path
import tempfile
import unittest

from delivery_audit import audit
from finalize import finalize
from test_measure_uturn import fixture


class DeliveryAuditTest(unittest.TestCase):
    def setUp(self):
        root = Path.cwd() / ".runtime-work"
        root.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=root)
        self.folder = Path(self.tmp.name)
        fixture(self.folder, "authorized_opening")
        case = json.loads((self.folder / "request.json").read_text())["case_id"]
        (self.folder / "config.json").write_text(json.dumps({"selected_case_id": case}) + "\n")
        (self.folder / "construction.json").write_text(json.dumps({
            "case_id": case, "recording_description": "Synthetic source test"}) + "\n")
        (self.folder / "trace.jsonl").write_text('{"time_s":0}\n')
        (self.folder / "body_history.jsonl").write_text('{"frame":0}\n')
        (self.folder / "capture").mkdir()
        (self.folder / "capture/evidence.jsonl").write_text('{"frame":0}\n')
        for name in ("overview", "approach", "median_reference", "driver_reference"):
            (self.folder / (name + ".mkv")).write_bytes(b"diagnostic-placeholder")
        self.report = self.folder / "analysis-report.json"
        finalize(self.folder, self.report)

    def tearDown(self):
        self.tmp.cleanup()

    def test_diagnostic_source_join_and_original_gate(self):
        receipt = audit(self.folder, self.report, diagnostic=True)
        self.assertTrue(receipt["source_joins_passed"])
        self.assertFalse(receipt["physical_or_legal_acceptance"])
        with self.assertRaisesRegex(ValueError, "provenance differs"):
            audit(self.folder, self.report)

    def test_changed_authority_and_measurement_are_rejected(self):
        authority = self.folder / "authority-source.json"
        authority.write_text('{"public_authority_establishment":"changed"}\n')
        with self.assertRaisesRegex(ValueError, "authority source hash"):
            audit(self.folder, self.report, diagnostic=True)
        authority.write_text('{"public_authority_establishment":"unassessed"}\n')
        report = json.loads(self.report.read_text())
        report["measurements"]["divider_crossing"]["value"]["opening_overlap_frames"] = -1
        self.report.write_text(json.dumps(report) + "\n")
        with self.assertRaisesRegex(ValueError, "measurement or source hash"):
            audit(self.folder, self.report, diagnostic=True)

    def test_missing_camera_and_short_channel_rejected(self):
        (self.folder / "overview.mkv").unlink()
        with self.assertRaisesRegex(ValueError, "camera source"):
            audit(self.folder, self.report, diagnostic=True)
        (self.folder / "overview.mkv").write_bytes(b"diagnostic-placeholder")
        channel = self.folder / "channels/ego_pose.jsonl"
        channel.write_text(channel.read_text().splitlines()[0] + "\n")
        with self.assertRaisesRegex(ValueError, "600-frame channel"):
            audit(self.folder, self.report, diagnostic=True)


if __name__ == "__main__":
    unittest.main()
