"""Verify saved stopped distance comes from original centre geometry."""
import json
import sys
import tempfile
import unittest
from pathlib import Path


FOLDER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FOLDER))
import stopped_finalizer


def box(center):
    return [[center-2, -1], [center+2, -1], [center+2, 1], [center-2, 1]]


class StoppedFinalizerTests(unittest.TestCase):
    def test_original_centres_and_missing_state(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            case = FOLDER.name + "__stopped_drive_to_450ft"
            config = {"law_id": "NRS-484B-710", "selected_case_id": case,
                      "fire_branch": "stopped_drive_to", "target_distance_ft": 450,
                      "case": {"recording_description": {"channels": []}}}
            context = {"alarm_response_source": "authored stopped alarm premise",
                       "apparatus_answered_alarm": True,
                       "subject_authorized_emergency": False,
                       "subject_official_business": False}
            (root / "config.json").write_text(json.dumps(config))
            (root / "fire_context.json").write_text(json.dumps(context))
            apparatus_center = 2 + 450 / 3.280839895013123
            data = {
                "video_frames.jsonl": [{"video_frame": i, "carla_frame": 20+i,
                                        "time_s": i/20} for i in range(3)],
                "trace.jsonl": [{"frame": 20+i, "time_s": i/20} for i in range(3)],
                "participant_footprints.jsonl": [
                    {"frame": 20+i, "time_s": i/20,
                     "ego_id": "ego", "apparatus_id": "apparatus",
                     "ego_corners": box(i), "apparatus_corners": box(apparatus_center)}
                    for i in range(3)],
                "participant_state.jsonl": [
                    {"frame": 20+i, "time_s": i/20,
                     "apparatus_moving": False, "ego_moving": True,
                     "ego_following": False, "ego_parked": False,
                     "warning_lamp": True, "siren": None}
                    for i in range(3)],
            }
            for name, rows in data.items():
                (root / name).write_text("".join(json.dumps(row) + "\n" for row in rows))
            report = stopped_finalizer.analyze(root)
            observed = report["measurements"]["fire_boundary_observation"]["value"]
            self.assertEqual(observed["boundary_measurement"], "centre_distance_ft")
            self.assertEqual(observed["active_frame_count"], 2)
            result = stopped_finalizer.build_result(root, report)
            self.assertEqual(result["recording_evidence"][0]["name"], "fire_centre_distance_ft")
            self.assertAlmostEqual(result["target_checks"][0]["measured"], 450)
            self.assertEqual(len((root / "fire_centre_distance_ft.jsonl").read_text().splitlines()), 3)
            self.assertFalse(result["physical_acceptance_claimed"])
            (root / "participant_state.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: participant_state.jsonl"):
                stopped_finalizer.analyze(root)


if __name__ == "__main__":
    unittest.main()
