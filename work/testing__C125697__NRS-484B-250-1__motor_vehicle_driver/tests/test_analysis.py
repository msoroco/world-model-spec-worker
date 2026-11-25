import json
from pathlib import Path
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import analysis
from test_saved_comparison import attempt


def staged(root: Path, suffix: str, ego_entry: int):
    attempt(root, suffix, ego_entry)
    construction = json.loads((HERE / ("construction-" + suffix + ".json")).read_text())
    files = {item["path"]: item["content"] for item in construction["files"]}
    (root / "construction.json").write_text(json.dumps(construction))
    (root / "config.json").write_text(files["config.json"])
    (root / "case-plan.json").write_text(files["case-plan.json"])
    source = (root / "source-manifest.json").read_bytes()
    (root / "original-source-manifest.json").write_bytes(source)
    (root / "source-manifest.json").unlink()
    (root / "fixture-provenance.json").write_text(json.dumps({
        "diagnostic_fixture": True, "physical_acceptance_claimed": False}))
    original = json.loads((root / "native_trace.json").read_text())
    rows = original["frames"]
    (root / "trace.jsonl").write_text("".join(json.dumps({
        "frame": row["native_frame_id"], "time_s": row["native_elapsed_seconds"],
        "position": {"x": 0, "y": 0, "z": 0}, "heading_deg": 0,
        "speed_mps": 0}) + "\n" for row in rows))
    (root / "video_frames.jsonl").write_text("".join(json.dumps({
        "video_frame": i, "carla_frame": row["native_frame_id"],
        "native_frame": row["native_frame_id"],
        "time_s": row["native_elapsed_seconds"]}) + "\n"
        for i, row in enumerate(rows)))


class AnalysisTests(unittest.TestCase):
    def test_selected_saved_only_analysis_and_negative_frame_join(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for suffix, entry in (("precedence", 60), ("advance", 45)):
                path = root / suffix
                staged(path, suffix, entry)
                report = analysis.analyze(path, path / "analysis-report.json")
                result = json.loads((path / "result.json").read_text())
                self.assertEqual(report["case_id"], result["case_id"])
                self.assertEqual(len(result["recording_evidence"]), 4)
                self.assertTrue(result["target_checks"][1]["matched"])
                self.assertFalse(result["physical_acceptance_claimed"])
                self.assertEqual(len((path / "channels" / "intersection_body_history.jsonl").read_text().splitlines()), 900)
            bad = root / "broken"
            staged(bad, "precedence", 60)
            rows = (bad / "video_frames.jsonl").read_text().splitlines()
            changed = json.loads(rows[10])
            changed["carla_frame"] += 3
            rows[10] = json.dumps(changed)
            (bad / "video_frames.jsonl").write_text("\n".join(rows) + "\n")
            with self.assertRaisesRegex(ValueError, "identity differs"):
                analysis.analyze(bad, bad / "analysis-report.json")


if __name__ == "__main__":
    unittest.main()
