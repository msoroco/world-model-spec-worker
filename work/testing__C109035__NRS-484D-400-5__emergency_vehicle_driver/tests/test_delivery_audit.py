"""Independent delivery audit positive and negative original-source probes."""
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import camera_recorder
import test_native_capture
from delivery_audit import audit


class DeliveryAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_native_capture.CaptureTests(
            methodName="test_full_source_seal_and_distinct_command_readback")
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.case_id = test_native_capture.CASE
        image = types.SimpleNamespace(width=2, height=2,
                                      raw_data=bytes([5, 9, 17, 255] * 4))

        def read(frame):
            image.frame = frame
            return {name: image for name in camera_recorder.CAMERAS}

        recorder = camera_recorder.CameraRecorder(
            self.fixture.folder / "out", read, case_id=self.case_id,
            source_ids={name: "synthetic-" + name for name in camera_recorder.CAMERAS},
            sizes={name: (2, 2) for name in camera_recorder.CAMERAS})

        def drive(ego, pedestrian, tick):
            location, rotation = ego.transform
            ego.transform = ((location[0] if tick == 0 else
                              -60 + 85 * tick / 899, location[1], location[2]), rotation)

        self.receipt = self.fixture.run_capture(camera_capture=recorder,
                                                 drive_step=drive)
        self.output = self.fixture.folder / "out"
        self.status = {"case_id": self.case_id, "capture": self.receipt,
                       "errors": [], "restoration": {"restored": True},
                       "physical_acceptance_claimed": False}
        self.save_status()

    def save_status(self):
        (self.output / "native-run-status.json").write_text(
            json.dumps(self.status) + "\n")

    def test_synthetic_original_sources_join_without_physical_claim(self):
        report = audit(self.output, case_id=self.case_id, diagnostic_test=True)
        self.assertEqual(report["frame_count"], 900)
        self.assertEqual(report["decoded_original_pixels"], 3600)
        self.assertEqual(report["physical_checks"]["maneuver"]["status"], "met")
        self.assertFalse(report["participant_visibility_verified"])
        self.assertFalse(report["physical_acceptance_claimed"])

    def test_restoration_failure_rejected(self):
        self.status["restoration"]["restored"] = False
        self.save_status()
        with self.assertRaisesRegex(ValueError, "restoration differs"):
            audit(self.output, case_id=self.case_id, diagnostic_test=True)

    def test_review_required_for_nondiagnostic_acceptance(self):
        with self.assertRaisesRegex(ValueError, "profile"):
            audit(self.output, case_id=self.case_id, diagnostic_test=False)

    def test_stopped_approach_rejected(self):
        path = self.output / "actor_trace.jsonl"
        actors = [json.loads(line) for line in path.read_text().splitlines()]
        for row in actors:
            row["ego"]["x_m"] = -60.0
        path.write_text("".join(json.dumps(row) + "\n" for row in actors))
        import hashlib
        self.receipt["sources"]["actor_trace"]["sha256"] = hashlib.sha256(
            path.read_bytes()).hexdigest()
        (self.output / "capture_receipt.json").write_text(
            json.dumps(self.receipt) + "\n")
        self.status["capture"] = self.receipt
        self.save_status()
        media_path = self.output / "camera_media.json"
        media = json.loads(media_path.read_text())
        media["capture_receipt_sha256"] = hashlib.sha256(
            (self.output / "capture_receipt.json").read_bytes()).hexdigest()
        media_path.write_text(json.dumps(media) + "\n")
        with self.assertRaisesRegex(ValueError, "approach did not complete"):
            audit(self.output, case_id=self.case_id, diagnostic_test=True)


if __name__ == "__main__":
    unittest.main()
