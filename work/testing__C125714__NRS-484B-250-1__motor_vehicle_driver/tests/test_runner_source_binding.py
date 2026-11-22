"""The Native handoff must receive the exact inspected context path."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner import main, resolve_reviewed_source


class RunnerSourceBinding(unittest.TestCase):
    def test_all_seven_relative_packets_resolve_from_scene_directory(self):
        for kind in ("precedence", "advance", "other_later", "opposite_straight",
                     "opposite_intends_left", "opposite_makes_left", "wide_same_crossing"):
            folder = ROOT if kind == "precedence" else ROOT / "cases" / kind
            scene_path = folder / "scene.json"
            scene = json.loads(scene_path.read_text())
            source = resolve_reviewed_source(scene, scene_path)
            self.assertEqual(source, (folder / "diagnostic-context.json").resolve())

    def test_launch_passes_resolved_packet_from_another_working_directory(self):
        scene_path = ROOT / "cases" / "opposite_makes_left" / "scene.json"
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            try:
                os.chdir(directory)
                with mock.patch.object(sys, "argv", ["runner.py", "--scene", str(scene_path),
                                                    "--output-dir", directory]), \
                     mock.patch("native_capture.run_native") as run:
                    main()
            finally:
                os.chdir(previous)
            passed = run.call_args.args[0]
            self.assertEqual(Path(passed["reviewed_context_source"]),
                             scene_path.with_name("diagnostic-context.json").resolve())
            self.assertEqual(passed["case_id"],
                             ROOT.name + "__opposite_makes_left")

    def test_changed_packet_hash_rejected(self):
        scene_path = ROOT / "scene.json"
        scene = json.loads(scene_path.read_text())
        scene["reviewed_context_sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash differs"):
            resolve_reviewed_source(scene, scene_path)


if __name__ == "__main__":
    unittest.main()
