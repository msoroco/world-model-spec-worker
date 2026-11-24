"""Real FFmpeg profile proof and deliberate wrong-rate rejection."""
import subprocess
import sys
import tempfile
import unittest
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from original_media_profile import CAMERAS, audit


class MediaProfileTest(unittest.TestCase):
    def test_four_saved_profiles_and_wrong_rate(self):
        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as directory:
            root = Path(directory)
            for name in CAMERAS:
                width, height = (1920, 1080) if name == "overview" else (1280, 720)
                subprocess.run(
                    ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                     "-f", "lavfi", "-i", f"color=c=red:s={width}x{height}:r=20",
                     "-frames:v", "2", "-an", "-c:v", "ffv1", "-threads", "1",
                     str(root / (name + ".mkv"))], check=True, capture_output=True)
            (root / "camera-frame-map.jsonl").write_text(
                "\n".join(json.dumps({"frame": frame, "elapsed_seconds": (frame - 1) / 20,
                                      "camera_names": list(CAMERAS)})
                          for frame in (1, 2)) + "\n")
            self.assertEqual(set(audit(root)["cameras"]), set(CAMERAS))
            self.assertEqual(audit(root)["frame_map_count"], 2)
            (root / "camera-frame-map.jsonl").write_text(json.dumps(
                {"frame": 1, "elapsed_seconds": 0.0, "camera_names": list(CAMERAS)}) + "\n")
            with self.assertRaisesRegex(ValueError, "decoded frame count differs"):
                audit(root)
            (root / "camera-frame-map.jsonl").write_text("\n".join(json.dumps(row) for row in [
                {"frame": 1, "elapsed_seconds": 0.0, "camera_names": list(CAMERAS)},
                {"frame": 3, "elapsed_seconds": .05, "camera_names": list(CAMERAS)}]) + "\n")
            with self.assertRaisesRegex(ValueError, "not contiguous"):
                audit(root)
            (root / "camera-frame-map.jsonl").write_text("\n".join(json.dumps(row) for row in [
                {"frame": 1, "elapsed_seconds": 0.0, "camera_names": list(CAMERAS)},
                {"frame": 2, "elapsed_seconds": .1, "camera_names": list(CAMERAS)}]) + "\n")
            with self.assertRaisesRegex(ValueError, "not contiguous"):
                audit(root)
            (root / "camera-frame-map.jsonl").write_text("\n".join(json.dumps(row) for row in [
                {"frame": 1, "elapsed_seconds": 0.0, "camera_names": list(CAMERAS)},
                {"frame": 2, "elapsed_seconds": .05, "camera_names": list(CAMERAS[:-1])}]) + "\n")
            with self.assertRaisesRegex(ValueError, "wrong camera identity"):
                audit(root)
            (root / "camera-frame-map.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "frame map missing"):
                audit(root)
            (root / "camera-frame-map.jsonl").write_text(
                "\n".join(json.dumps({"frame": frame, "elapsed_seconds": (frame - 1) / 20,
                                      "camera_names": list(CAMERAS)})
                          for frame in (1, 2)) + "\n")
            extra = root / "extra.mkv"
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-i", str(root / "approach.mkv"), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono",
                 "-frames:v", "2", "-t", "0.1", "-map", "0:v", "-map", "1:a",
                 "-c:v", "copy", "-c:a", "pcm_s16le", str(extra)],
                check=True, capture_output=True)
            extra.replace(root / "approach.mkv")
            with self.assertRaisesRegex(ValueError, "stream count invalid: approach"):
                audit(root)
            subprocess.run(
                ["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                 "-f", "lavfi", "-i", "color=c=red:s=1280x720:r=10",
                 "-frames:v", "2", "-an", "-c:v", "ffv1", "-threads", "1",
                 str(root / "approach.mkv")], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "encoding profile differs: approach"):
                audit(root)


if __name__ == "__main__":
    unittest.main()
