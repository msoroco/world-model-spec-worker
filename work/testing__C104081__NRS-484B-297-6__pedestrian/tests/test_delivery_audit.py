import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
from delivery_audit import CAMERAS, audit_saved
from test_saved_measurement import SavedMeasurementTests


class DeliverySourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SavedMeasurementTests("test_blocked_intervening_lane_use_and_return")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.case_id = self.fixture.case_id
        names = ("video_frames.jsonl", "pedestrian_history.jsonl",
                 "obstruction_history.jsonl", "traffic_history.jsonl")
        for name in names:
            old = [json.loads(line) for line in (self.root / name).read_text().splitlines()]
            rows = []
            for i in range(900):
                stage = min(6, i * 7 // 900)
                row = dict(old[stage])
                if name == "video_frames.jsonl":
                    row.update(carla_frame=500 + i, video_frame=i, time_s=1 + i * .05)
                else:
                    row.update(frame=500 + i, time_s=1 + i * .05)
                rows.append(row)
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture._seal()
        self._seal_media()

    def _seal_media(self):
        packet_path = self.root / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        packet["camera_media"] = {}
        for camera in CAMERAS:
            path = self.root / (camera + ".txt")
            path.write_text("diagnostic sealed bytes for " + camera + "\n")
            packet["camera_media"][camera] = {
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "frame_count": 900, "fps": 20,
            }
        packet_path.write_text(json.dumps(packet) + "\n")

    def test_diagnostic_source_integrity_does_not_claim_delivery(self):
        receipt = audit_saved(self.root, self.case_id, diagnostic=True)
        self.assertEqual(receipt["original_frame_count"], 900)
        self.assertEqual(receipt["source_integrity"], "passed")
        self.assertFalse(any([
            receipt["checks"]["native_source"], receipt["checks"]["all_participants"],
            receipt["checks"]["full_video_decode"], receipt["checks"]["actual_pixels"],
            receipt["checks"]["physical_completion"],
        ]))
        self.assertTrue(receipt["checks"]["time_join"])

    def test_diagnostic_source_rejected_by_default(self):
        with self.assertRaisesRegex(ValueError, "requires original saved acquisition"):
            audit_saved(self.root, self.case_id)

    def test_media_digest_and_escape_rejected(self):
        with (self.root / "overview.txt").open("a") as stream:
            stream.write("altered\n")
        with self.assertRaisesRegex(ValueError, "camera media digest mismatch"):
            audit_saved(self.root, self.case_id, diagnostic=True)
        self._seal_media()
        path = self.root / "source-packet.json"
        packet = json.loads(path.read_text())
        packet["camera_media"]["overview"]["path"] = "../outside.txt"
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "escapes saved attempt"):
            audit_saved(self.root, self.case_id, diagnostic=True)

    def test_missing_camera_and_frame_rejected(self):
        packet_path = self.root / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        packet["camera_media"].pop("approach")
        packet_path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "four-camera"):
            audit_saved(self.root, self.case_id, diagnostic=True)
        self._seal_media()
        lines = (self.root / "video_frames.jsonl").read_text().splitlines()
        (self.root / "video_frames.jsonl").write_text("\n".join(lines[:-1]) + "\n")
        self.fixture._seal()
        self._seal_media()
        with self.assertRaisesRegex(ValueError, "history lengths"):
            audit_saved(self.root, self.case_id, diagnostic=True)

    def test_foreign_case_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown exact pedestrian case"):
            audit_saved(self.root, self.case_id + "_extra", diagnostic=True)

    def test_sealed_attempt_from_different_planned_case_rejected(self):
        clear_id = self.case_id.replace("blocked_intervening", "clear_intervening")
        path = self.root / "source-packet.json"
        packet = json.loads(path.read_text())
        packet["case_id"] = clear_id
        path.write_text(json.dumps(packet) + "\n")
        with self.assertRaisesRegex(ValueError, "does not match exact planned case"):
            audit_saved(self.root, clear_id, diagnostic=True)

    def test_full_four_camera_decode_with_diagnostic_video(self):
        packet_path = self.root / "source-packet.json"
        packet = json.loads(packet_path.read_text())
        for camera in CAMERAS:
            path = self.root / (camera + ".mp4")
            subprocess.run(
                ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                 "color=c=black:s=16x16:r=20", "-frames:v", "900",
                 "-an", "-c:v", "mpeg4", str(path)], check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            packet["camera_media"][camera] = {
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "frame_count": 900, "fps": 20,
            }
        packet_path.write_text(json.dumps(packet) + "\n")
        receipt = audit_saved(self.root, self.case_id, diagnostic=True, decode_media=True)
        self.assertTrue(receipt["checks"]["full_video_decode"])
        self.assertFalse(receipt["checks"]["actual_pixels"])
        self.assertFalse(receipt["checks"]["physical_completion"])
        self.assertFalse(receipt["decoded_camera_media"]["overview"]["profile_dimensions"])

    def test_sealed_nonvideo_bytes_fail_decode(self):
        with self.assertRaisesRegex(ValueError, "camera probe failed"):
            audit_saved(self.root, self.case_id, diagnostic=True, decode_media=True)

    def test_cli_positive_diagnostic_and_negative_default(self):
        cmd = [sys.executable, str(ROOT / "delivery_audit.py"),
               "--attempt", str(self.root), "--case", self.case_id]
        positive = subprocess.run(cmd + ["--diagnostic"], capture_output=True, text=True)
        self.assertEqual(positive.returncode, 0, positive.stderr)
        self.assertEqual(json.loads(positive.stdout)["source_integrity"], "passed")
        negative = subprocess.run(cmd, capture_output=True, text=True)
        self.assertNotEqual(negative.returncode, 0)
        self.assertIn("delivery requires original saved acquisition", negative.stderr)


if __name__ == "__main__":
    unittest.main()
