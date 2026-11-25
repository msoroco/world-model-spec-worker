import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location(
    "finalize_original_sources", ROOT / "finalize_original_sources.py")
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)
from freight_contract import SourceError
from test_saved_comparison import fixture


class FinalizeOriginalSourcesTests(unittest.TestCase):
    def test_finalizer_joins_raw_motion_and_source_seals(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            for variant in ("freight_loading", "freight_unloading", "no_freight_activity",
                            "noncommercial_loading", "outside_posted_time", "outside_yellow_zone"):
                with self.subTest(variant=variant):
                    attempt = Path(tmp) / variant
                    manifest = fixture(attempt, variant)
                    original = json.loads(Path(manifest["sources"]["native_result"]["path"]).read_text())
                    frames = []
                    motion = []
                    for index, sample in enumerate(original["frames"]):
                        native_frame = index + 101
                        frame = {"video_frame": index, "native_frame": native_frame,
                                 "time_s": sample["time_s"]}
                        frames.append(json.dumps(frame))
                        motion.append(json.dumps(dict(sample, native_frame=native_frame)))
                    (attempt / "frame-map.jsonl").write_text("\n".join(frames) + "\n")
                    (attempt / "freight_motion.jsonl").write_text("\n".join(motion) + "\n")
                    result = finalizer.finalize(attempt, case_id=manifest["case_id"],
                                                source_refs=manifest["sources"])
                    self.assertEqual(result["case_id"], manifest["case_id"])
                    packet = json.loads(Path(result["sources"]["native_result"]["path"]).read_text())
                    self.assertEqual(packet["posted_window_check"]["inside"],
                                     variant != "outside_posted_time")
                    self.assertEqual(len(packet["frames"]), 900)

    def test_finalizer_rejects_unjoined_original_motion(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            attempt = Path(tmp) / "attempt"
            manifest = fixture(attempt, "freight_loading")
            (attempt / "frame-map.jsonl").write_text("{}\n" * 900)
            (attempt / "freight_motion.jsonl").write_text("{}\n" * 900)
            with self.assertRaisesRegex(SourceError, "video/motion frame join"):
                finalizer.finalize(attempt, case_id=manifest["case_id"],
                                   source_refs=manifest["sources"])
