import json
import sys
import tempfile
import unittest
from pathlib import Path
from queue import Queue
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import runner
from yield_context import build
from yield_stage import KINDS, PREFIX, primary


class RunnerTests(unittest.TestCase):
    def test_each_exact_case_passes_cpu_config_and_status_packet(self):
        base = json.loads((ROOT / "config.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in KINDS:
                config = dict(base, selected_case_id=PREFIX + kind)
                stage = runner.validate_config(config)
                site = {"native_map_id": "signed-map", "intersection_id": 158209,
                        "native_yield_sign_id": 88,
                        "native_other_stop_sign_id": 90 if stage.other_stop_sign else None}
                path = runner._write_status_review(root, stage, site)
                context = build(stage, site, path)
                self.assertEqual(context["case_id"], PREFIX + kind)
                self.assertEqual(context["entrances"][1]["device"],
                                 "stop" if stage.other_stop_sign else "none")
                self.assertTrue(json.loads(path.read_text())["physical_road_status_confirmation_pending"])

    def test_camera_join_rejects_future_frame(self):
        queue = Queue()
        queue.put(NS(frame=102))
        with self.assertRaisesRegex(ValueError, "skipped Native frame"):
            runner.camera_frame(queue, 101)


if __name__ == "__main__":
    unittest.main()
