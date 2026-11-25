"""Four-camera decode is software proof only; frames are synthetic."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from cycle_lane_delivery import audit_delivery
import test_cycle_lane_original as fixture_module


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.OriginalAuditTests()
        self.fixture.setUp()
        root = self.fixture.root
        video = root / "synthetic.mkv"
        command = ["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                   "color=c=blue:size=64x64:rate=20:duration=45",
                   "-c:v", "mpeg4", "-q:v", "2", "-an", str(video)]
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        self.fixture.seal["cameras"] = {}
        for view in ("overview", "approach", "reference_corner", "driver_reference"):
            target = root / (view + ".mkv")
            target.write_bytes(video.read_bytes())
            self.fixture.seal["cameras"][view] = {
                "path": target.name, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}
        video.unlink()
        fixture_module.write(root, "attempt-source.json", self.fixture.seal)

    def tearDown(self):
        self.fixture.tearDown()

    def check(self):
        return audit_delivery(self.fixture.root, self.fixture.site["sha256"],
                              self.fixture.exception["sha256"],
                              self.fixture.vehicle["sha256"])

    def test_full_decode_four_synthetic_views(self):
        report = self.check()
        self.assertEqual([v["frame_count"] for v in report["media"].values()], [900] * 4)
        self.assertFalse(report["checks"]["actual_pixels"])
        self.assertFalse(report["checks"]["physical_completion"])

    def test_corrupted_view_rejected(self):
        target = self.fixture.root / "approach.mkv"
        target.write_bytes(target.read_bytes()[:200])
        self.fixture.seal["cameras"]["approach"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
        fixture_module.write(self.fixture.root, "attempt-source.json", self.fixture.seal)
        with self.assertRaisesRegex(ValueError, "camera (frame metadata missing|45-second 20 Hz profile mismatch|probe failed)"):
            self.check()
