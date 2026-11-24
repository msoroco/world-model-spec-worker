import os
from pathlib import Path
import sys
import hashlib
import json
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dual_green import EvidenceError
from native_runner import _live_packet, run


class NativeRunnerTests(unittest.TestCase):
    def test_unsourced_native_launch_rejected_before_client_import(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(EvidenceError, "Reviewed original dual-aspect"):
                run("127.0.0.1", 2000, ROOT, ROOT.name + "__dual_clear")

    def test_live_lamp_copies_frame_image_absent_from_site_prelist(self):
        scratch = ROOT.parents[1] / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            base = Path(temporary)
            source = base / "observer"
            output = base / "attempt"
            source.mkdir()
            output.mkdir()
            image = source / "frames" / "lamp-101.png"
            image.parent.mkdir()
            image.write_bytes(b"original frame pixels")
            observed = {"path": "frames/lamp-101.png",
                        "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}
            packet = {"frame": 101, "observer_method": "independent_camera_frame_review",
                      "original_observation": observed}
            (source / "lamp-101.json").write_text(json.dumps(packet), encoding="utf-8")
            ref = _live_packet(source, output, "lamp-101.json", 101)
            self.assertEqual(ref["path"], "lamp-101.json")
            self.assertEqual((output / observed["path"]).read_bytes(), image.read_bytes())
            self.assertEqual((output / "lamp-101.json").read_bytes(),
                             (source / "lamp-101.json").read_bytes())


if __name__ == "__main__":
    unittest.main()
