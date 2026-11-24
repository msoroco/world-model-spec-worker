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
from prepare_review import officer_template
from yield_context import build
from yield_stage import KINDS, PREFIX, primary


class RunnerTests(unittest.TestCase):
    def test_each_exact_case_passes_cpu_config_and_status_packet(self):
        base = json.loads((ROOT / "config.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for kind in KINDS:
                config = dict(base, selected_case_id=PREFIX + kind,
                              case=dict(base["case"], case_id=PREFIX + kind))
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

    def test_officer_review_template_requires_candidate_and_original_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "intersection_context.json").write_text(json.dumps({
                "case_id": PREFIX + "officer_control_exception"}) + "\n")
            (root / "officer-candidate.json").write_text(json.dumps({
                "format": "worker-officer-candidate-construction", "actor_id": 17,
                "police_authority_judgment": "unresolved"}) + "\n")
            (root / "video_frames.jsonl").write_text(json.dumps({"carla_frame": 101}) + "\n")
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (name + ".mkv")).write_bytes(name.encode())
            review = officer_template(root)
            self.assertEqual(review["officer_actor_id"], 17)
            self.assertIsNone(review["control_observed_at_entry"])
            self.assertEqual(review["reviewed_carla_frames"], [101])
            (root / "officer-candidate.json").unlink()
            with self.assertRaises(FileNotFoundError):
                officer_template(root)


if __name__ == "__main__":
    unittest.main()
