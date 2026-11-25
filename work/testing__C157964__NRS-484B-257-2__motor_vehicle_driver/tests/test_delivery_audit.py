"""Reject changed original sources and synthetic physical acceptance."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit, verify_other_entrance


class DeliveryAuditTests(unittest.TestCase):
    def test_other_entrance_native_lane_and_review_join(self):
        config = {"site": {"other_lane": [157966, 1]}}
        packet = {"review": {"other_entrance_road_id": 157966}}
        capture = {"other_lane_readback": [157966, 1]}
        self.assertEqual(verify_other_entrance(config, packet, capture), 157966)
        with self.assertRaisesRegex(ValueError, "Native lane join differs"):
            verify_other_entrance(config, packet,
                                  {"other_lane_readback": [157964, -1]})

    def setUp(self):
        self.case_id = HERE.name + "__officer_controls_go"
        self.source = HERE.parents[1] / ".runtime-work/c157964-sub2/compatibility-go"
        if not self.source.is_dir():
            self.skipTest("Diagnostic compatibility source is local to the worker workspace")
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name) / "attempt"
        shutil.copytree(self.source, self.attempt, ignore=shutil.ignore_patterns("tests", "channels", "converted"))

    def test_source_bound_positive_and_native_rejection(self):
        self.assertTrue(audit(self.attempt, self.case_id, True)["software_audit_passed"])
        with self.assertRaisesRegex(ValueError, "Native original provenance required"):
            audit(self.attempt, self.case_id)

    def test_changed_actor_history_rejected(self):
        path = self.attempt / "officer_history.jsonl"
        lines = path.read_text().splitlines()
        row = json.loads(lines[1])
        row["officer_direction_observed"] = "hold"
        lines[1] = json.dumps(row)
        path.write_text("\n".join(lines) + "\n")
        with self.assertRaisesRegex(ValueError, "reviewer and actor history disagree"):
            audit(self.attempt, self.case_id, True)

    def test_changed_camera_rejected(self):
        with (self.attempt / "overview.mkv").open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "camera source hash changed"):
            audit(self.attempt, self.case_id, True)

    def test_missing_measurement_source_rejected(self):
        (self.attempt / "officer_review.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing original source"):
            audit(self.attempt, self.case_id, True)


if __name__ == "__main__":
    unittest.main()
