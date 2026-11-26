"""Source-shaped software fixtures; never original Native evidence."""

import json
from pathlib import Path
import tempfile
import unittest

from finalize import derive, finalize
from scene import FRAMES, open_drive, target


class SavedSourceTest(unittest.TestCase):
    def make_fixture(self, root):
        root = Path(root)
        (root / "capture").mkdir()
        (root / "road.xodr").write_text(open_drive())
        (root / "pass-context.json").write_text(json.dumps({"statutory_subject": "bicycle"}) + "\n")
        files = {name: (root / name).open("w") for name in (
            "participant-poses.jsonl", "trace.jsonl", "video_frames.jsonl",
            "capture/evidence.jsonl")}
        try:
            for i in range(FRAMES):
                planned = target("witness_1", i)
                frame = i + 100
                t = i / 20
                ego = {"blueprint_id": "vehicle.tesla.model3",
                       "center_xy_m": [planned.ego_x_m, planned.ego_y_m]}
                cycle = {"blueprint_id": "vehicle.bh.crossbike",
                         "center_xy_m": [planned.cyclist_x_m, planned.cyclist_y_m]}
                data = {
                    "participant-poses.jsonl": {"frame": frame, "video_frame": i, "time_s": t,
                                                "ego": ego, "cyclist": cycle, "left_blocker": None},
                    "trace.jsonl": {"frame": frame},
                    "video_frames.jsonl": {"carla_frame": frame, "time_s": t,
                                           "camera_native_frames": {name: frame for name in (
                                               "overview", "approach", "reference_corner", "driver_reference")}},
                    "capture/evidence.jsonl": {"original_frame": frame}}
                for name, row in data.items():
                    files[name].write(json.dumps(row) + "\n")
        finally:
            for stream in files.values():
                stream.close()

    def test_joined_lane_pass_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_fixture(root)
            measured = derive(root)
            self.assertLess(measured["first_left_frame"], measured["pass_first_frame"])
            self.assertEqual(measured["left_during_pass_frames"], measured["pass_frame_count"])
            self.assertFalse(measured["left_lane_available_verified"])
            (root / "road.xodr").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: road.xodr"):
                derive(root)

    def test_saved_channel_writer_is_unaccepted(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.make_fixture(root)
            case = "training__C247014__NRS-484B-270-2a__motor_vehicle_driver__witness_1"
            (root / "config.json").write_text(json.dumps({
                "case_id": case, "supported_case_ids": [case]}) + "\n")
            channels = [{"name": name, "unit": "structured"} for name in (
                "ego_pose", "cyclist_pose", "left_lane_occupancy", "drv.overtaking",
                "drv.lane_change", "rel.occupies")]
            (root / "construction.json").write_text(json.dumps({
                "case_id": case, "recording_description": {"channels": channels}}) + "\n")
            report = finalize(root, root / "analysis.json")
            self.assertFalse(report["physical_or_legal_acceptance"])
            result = json.loads((root / "result.json").read_text())
            self.assertFalse(result["accepted"])
            self.assertEqual(len(result["recording_evidence"]), 7)
            self.assertEqual(len((root / "channels" / "ego_pose.jsonl").read_text().splitlines()), 600)


if __name__ == "__main__":
    unittest.main()
