import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
import runner


class RunnerTests(unittest.TestCase):
    def test_exact_selected_scene_and_source_hash(self):
        self.assertTrue(runner.check().endswith("__destination_occupied_absent"))
        scratch = REPO / ".runtime-work" / "c111610-runner-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            root = Path(temporary)
            (root / "config.json").write_bytes((ROOT / "config.json").read_bytes())
            (root / "scene.json").write_bytes((ROOT / "scene.json").read_bytes())
            self.assertEqual(runner.check(root), runner.check())
            scene = json.loads((root / "scene.json").read_text())
            scene["official_device_condition"] = "operating"
            (root / "scene.json").write_text(json.dumps(scene) + "\n")
            with self.assertRaisesRegex(ValueError, "scene source changed"):
                runner.check(root)

    def test_native_capture_needs_explicit_output(self):
        with self.assertRaisesRegex(ValueError, "output directory required"):
            runner.main([])

    def test_materialized_bundle_keeps_source_capture_under_capture(self):
        scratch = REPO / ".runtime-work" / "c111610-runner-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as temporary:
            source = Path(temporary)
            (source / "site.json").write_text("{}\n")
            (source / "exception.json").write_text("{}\n")
            import live_entrypoint
            with patch.dict("os.environ", {"C111610_SITE_ROOT": str(source)}), \
                 patch.object(live_entrypoint, "run") as capture:
                self.assertEqual(runner.main(["--output-dir", str(source / "attempt")]), 0)
            self.assertEqual(capture.call_args.kwargs["output"], source / "attempt/capture")


if __name__ == "__main__": unittest.main()
