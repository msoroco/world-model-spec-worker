"""Full original-video decode must fail closed on a bad FFV1 stream."""
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from production_delivery_audit import ffprobe_frames


class FullDecodeTests(unittest.TestCase):
    def test_complete_decode_is_required_after_frame_count(self):
        probe = subprocess.CompletedProcess([], 0,
            stdout=json.dumps({"streams": [{"codec_name": "ffv1", "nb_read_frames": "900"}]}),
            stderr="")
        decoder_failure = subprocess.CalledProcessError(1, ["ffmpeg"], stderr=b"damaged frame")
        with patch("production_delivery_audit.subprocess.run",
                   side_effect=[probe, decoder_failure]) as run:
            with self.assertRaises(subprocess.CalledProcessError):
                ffprobe_frames(Path("original.mkv"))
        decode = run.call_args_list[1].args[0]
        self.assertIn("-xerror", decode)
        self.assertEqual(decode[-3:], ["-f", "null", "-"])
        self.assertIn("0:v:0", decode)

    def test_success_requires_probe_and_full_decode(self):
        probe = subprocess.CompletedProcess([], 0,
            stdout=json.dumps({"streams": [{"codec_name": "ffv1", "nb_read_frames": "900"}]}),
            stderr="")
        decoded = subprocess.CompletedProcess([], 0, stdout=b"", stderr=b"")
        with patch("production_delivery_audit.subprocess.run", side_effect=[probe, decoded]) as run:
            self.assertEqual(ffprobe_frames(Path("original.mkv")), 900)
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
