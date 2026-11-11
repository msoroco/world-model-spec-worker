import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


source = Path(__file__).resolve().parents[1] / "fire_finalizer.py"
spec = importlib.util.spec_from_file_location("fire_finalizer", source)
finalizer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(finalizer)


def box(x0, x1):
    return [[x0, -1], [x1, -1], [x1, 1], [x0, 1]]


class FireFinalizerTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.config = {"law_id": "NRS-484B-710", "selected_case_id": "fire-at-500",
                       "fire_branch": "traveling_follow"}
        self.context = {"alarm_response_source": "authored dispatch record",
                        "apparatus_answered_alarm": True,
                        "subject_authorized_emergency": False,
                        "subject_official_business": False}
        (self.root / "config.json").write_text(json.dumps(self.config))
        (self.root / "fire_context.json").write_text(json.dumps(self.context))
        feet_per_metre = finalizer.branch_measurement._distance.FEET_PER_METRE
        for name, rows in {
            "video_frames.jsonl": [
                {"video_frame": i, "carla_frame": 20 + i, "time_s": i / 20}
                for i in range(2)],
            "trace.jsonl": [
                {"frame": 20 + i, "time_s": i / 20, "position_m": [i, 0]}
                for i in range(2)],
            "participant_footprints.jsonl": [
                {"frame": 20 + i, "time_s": i / 20, "ego_id": "ego",
                 "apparatus_id": "apparatus", "ego_corners": box(i, i + 4),
                 "apparatus_corners": box(i + 4 + 500 / feet_per_metre,
                                          i + 10 + 500 / feet_per_metre)}
                for i in range(2)],
            "participant_state.jsonl": [
                {"frame": 20 + i, "time_s": i / 20, "apparatus_moving": True,
                 "ego_moving": True, "ego_following": True, "ego_parked": False,
                 "warning_lamp": True, "siren": True}
                for i in range(2)],
        }.items():
            (self.root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_original_sources_produce_case_measurements(self):
        report = finalizer.analyze(self.root)
        self.assertEqual(report["case_id"], "fire-at-500")
        boundary = report["measurements"]["fire_boundary_observation"]
        self.assertEqual(boundary["value"]["at_500_frames"], [20, 21])
        self.assertEqual(boundary["value"]["active_frame_count"], 2)
        self.assertEqual(set(boundary["sources"]), {
            "config.json", "trace.jsonl", "video_frames.jsonl",
            "participant_footprints.jsonl", "participant_state.jsonl",
            "fire_context.json"})
        self.assertFalse(report["physical_acceptance_claimed"])

    def test_missing_original_state_is_rejected(self):
        (self.root / "participant_state.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: participant_state.jsonl"):
            finalizer.analyze(self.root)

    def test_wrong_original_frame_join_is_rejected(self):
        path = self.root / "video_frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[1]["carla_frame"] = 999
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        with self.assertRaisesRegex(ValueError, "trace/frame-map join failed"):
            finalizer.analyze(self.root)

    def test_context_is_separate_from_lamp_state(self):
        self.context["subject_authorized_emergency"] = True
        self.context["subject_official_business"] = True
        (self.root / "fire_context.json").write_text(json.dumps(self.context))
        report = finalizer.analyze(self.root)
        self.assertTrue(report["measurements"]["exception_context"]["value"]
                        ["subject_official_business"])
        self.assertTrue(report["measurements"]["fire_boundary_observation"]["value"]
                        ["at_500_frames"])

    def test_saved_result_keeps_physical_status_unverified(self):
        self.config["case"] = {"recording_description": {"channels": []}}
        (self.root / "config.json").write_text(json.dumps(self.config))
        result = finalizer.build_result(self.root, finalizer.analyze(self.root))
        self.assertFalse(result["setup_confirmed"])
        self.assertFalse(result["maneuver_completed"])
        self.assertEqual(len(result["video_references"]), 4)
        self.assertEqual(result["target_checks"][0]["measured"],
                         result["realized_observables"]["minimum_boundary_distance_ft"])

    def test_cli_positive_and_missing_source_negative(self):
        self.config["case"] = {"recording_description": {"channels": []}}
        (self.root / "config.json").write_text(json.dumps(self.config))
        runtime = Path(__file__).resolve().parents[3] / "runtime"
        environment = dict(os.environ, PYTHONPATH=str(runtime))
        command = [sys.executable, str(source), "--attempt", str(self.root),
                   "--output", str(self.root / "analysis-report.json")]
        positive = subprocess.run(command, text=True, capture_output=True, env=environment)
        self.assertEqual(positive.returncode, 0, positive.stderr)
        self.assertTrue((self.root / "result.json").is_file())
        (self.root / "analysis-report.json").unlink()
        (self.root / "result.json").unlink()
        (self.root / "participant_state.jsonl").unlink()
        negative = subprocess.run(command, text=True, capture_output=True, env=environment)
        self.assertNotEqual(negative.returncode, 0)
        self.assertIn("Missing required source: participant_state.jsonl", negative.stderr)


if __name__ == "__main__":
    unittest.main()
