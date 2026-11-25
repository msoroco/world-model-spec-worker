import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_native_witness import packet

FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
MODULE = FOLDER / "analysis.py"
spec = importlib.util.spec_from_file_location("c158196_analysis", MODULE)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
SCRATCH = Path(__file__).resolve().parents[3] / ".runtime-work" / "c158196-analysis-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)
CASE = "testing__C158196__NRS-484B-257-2__motor_vehicle_driver__sign_within_stop"


def prepare(root):
    (root / "config.json").write_text(json.dumps({"selected_case_id": CASE}) + "\n")
    history = packet()
    history.update(case_id=CASE, control_context="stop_sign")
    (root / "original-history.json").write_text(json.dumps(history) + "\n")
    rows = [json.dumps({"video_frame": i, "carla_frame": i,
                        "time_s": i / 20}) for i in range(900)]
    (root / "video_frames.jsonl").write_text("\n".join(rows) + "\n")
    acquisition = {}
    for name in ("original-history.json", "video_frames.jsonl"):
        acquisition[name] = {"kind": "original_native", "sha256": hashlib.sha256(
            (root / name).read_bytes()).hexdigest()}
    (root / "acquisition.json").write_text(json.dumps(acquisition) + "\n")


class AnalysisTest(unittest.TestCase):
    def test_saved_history_requires_original_hashes_and_full_frame_join(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            prepare(root)
            report = mod.analyze(root)
            self.assertEqual(report["measurements"]["intersection_approach"]["value"]["entry_frame"], 100)
            self.assertFalse(report["physical_acceptance_claimed"])
            (root / "video_frames.jsonl").write_text("{}\n")
            with self.assertRaisesRegex(ValueError, "stale original"):
                mod.analyze(root)

    def test_selected_case_and_native_video_join_cannot_drift(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
            root = Path(temporary)
            prepare(root)
            (root / "config.json").write_text(json.dumps({"selected_case_id": CASE + "-other"}) + "\n")
            with self.assertRaisesRegex(ValueError, "absent"):
                mod.analyze(root)
            prepare(root)
            rows = (root / "video_frames.jsonl").read_text().splitlines()
            row = json.loads(rows[400]); row["carla_frame"] = 399
            rows[400] = json.dumps(row)
            (root / "video_frames.jsonl").write_text("\n".join(rows) + "\n")
            acquisition = json.loads((root / "acquisition.json").read_text())
            acquisition["video_frames.jsonl"]["sha256"] = hashlib.sha256(
                (root / "video_frames.jsonl").read_bytes()).hexdigest()
            (root / "acquisition.json").write_text(json.dumps(acquisition) + "\n")
            with self.assertRaisesRegex(ValueError, "frame join"):
                mod.analyze(root)


if __name__ == "__main__":
    unittest.main()
