import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_sources import CAMERAS, write_camera_sources
from prepare_derived_media import prepare
from test_camera_sources import fixture


class DerivedMediaTests(unittest.TestCase):
    def test_saved_stage_decodes_four_original_archives_without_rewriting_them(self):
        with tempfile.TemporaryDirectory() as directory:
            original = Path(directory) / "original"
            frames = fixture(original)
            write_camera_sources(original, frames, diagnostic_fixture=True)
            stage = Path(directory) / "stage"
            shutil.copytree(original, stage)
            sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in stage.iterdir() if p.is_file()}
            receipt = prepare(stage, diagnostic_fixture=True)
            self.assertEqual(set(receipt["videos"]), set(CAMERAS))
            self.assertTrue(all(item["frames"] == 3 for item in receipt["videos"].values()))
            self.assertEqual(sources, {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in stage.iterdir() if p.is_file() and p.name in sources})
            reused = prepare(stage, diagnostic_fixture=True, reuse_existing=True)
            self.assertEqual(reused["videos"], receipt["videos"])
            with self.assertRaisesRegex(ValueError, "already exists"):
                prepare(stage, diagnostic_fixture=True)


if __name__ == "__main__":
    unittest.main()
