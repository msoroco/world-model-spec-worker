import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from native_camera_audit import audit
from native_sight_cameras import SPECS


class CameraAuditTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / ".runtime-work" / "c129731-test-tmp"
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inventory = {"case_id": "exact", "camera_sources": {}, "sources": {}}
        self.write_frames()
        for name, _, _ in SPECS:
            path = self.root / (name + ".mkv")
            path.write_bytes(("original " + name).encode())
            self.inventory["camera_sources"][name] = {
                "path": path.name, "source_kind": "original_native",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        self.write_inventory()

    def write_frames(self, frames=None):
        frames = frames if frames is not None else [
            {"frame": 100 + i, "time_s": round(i / 20, 6)} for i in range(900)]
        path = self.root / "frame_map.json"
        path.write_text(json.dumps({"frames": frames}) + "\n")
        self.inventory["sources"]["frame_map"] = {
            "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def write_inventory(self):
        (self.root / "inventory.json").write_text(json.dumps(self.inventory) + "\n")

    def fake_run(self, command, **kwargs):
        if command[0] == "ffprobe":
            name = Path(command[-1]).stem
            _, width, height = next(row for row in SPECS if row[0] == name)
            return type("Result", (), {"returncode": 0, "stdout": json.dumps({
                "streams": [{"codec_name": "ffv1", "nb_read_frames": "900",
                             "r_frame_rate": "20/1", "width": width, "height": height}]})})()
        return type("Result", (), {"returncode": 0})()

    def test_four_source_hash_profile_and_full_decode_receipt(self):
        with patch("native_camera_audit.subprocess.run", side_effect=self.fake_run) as run:
            result = audit(self.root)
        self.assertEqual(len(result["sources"]), 4)
        self.assertEqual(run.call_count, 8)
        self.assertTrue(all(source["full_decode_passed"]
                            for source in result["sources"].values()))
        self.assertEqual(result["frame_count"], 900)
        self.assertEqual(result["frame_map_sha256"],
                         self.inventory["sources"]["frame_map"]["sha256"])

    def test_tampered_video_and_missing_view_rejected(self):
        (self.root / "approach.mkv").write_bytes(b"altered")
        with patch("native_camera_audit.subprocess.run", side_effect=self.fake_run):
            with self.assertRaisesRegex(ValueError, "hash changed"):
                audit(self.root)
        del self.inventory["camera_sources"]["approach"]
        self.write_inventory()
        with self.assertRaisesRegex(ValueError, "exact four"):
            audit(self.root)

    def test_frame_map_tamper_and_discontinuous_time_rejected(self):
        frame_path = self.root / "frame_map.json"
        frame_path.write_text("{}\n")
        with self.assertRaisesRegex(ValueError, "frame map hash changed"):
            audit(self.root)
        frames = [{"frame": 100 + i, "time_s": round(i / 20, 6)}
                  for i in range(900)]
        frames[450]["time_s"] += 0.2
        self.write_frames(frames)
        self.write_inventory()
        with self.assertRaisesRegex(ValueError, "not contiguous at 20 Hz"):
            audit(self.root)


if __name__ == "__main__":
    unittest.main()
