"""CPU source-join and negative-source checks for the at-rest angle meter."""
import json
import tempfile
import unittest
from pathlib import Path

from saved_angle import ASSIGNMENT, measure


CASE = ASSIGNMENT + "__selected_03f318de__condition_a"


def write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True) + "\n")


def write_rows(path, values):
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in values))


class SavedAngle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c385967-angle-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.provenance = "synthetic_cpu_fixture"
        write(self.root / "official_device.json", {
            "provenance": self.provenance, "official_device_review_required": True,
            "native_road_id": 1, "governs_space_id": "angle_space_1",
            "indicated_angle_to_curb_deg": 45})
        write(self.root / "road_geometry.json", {
            "provenance": self.provenance, "native_road_id": 1,
            "space_id": "angle_space_1", "curb_tangent_heading_deg": 0,
            "curb_side": "right"})
        write(self.root / "parking_context.json", {
            "provenance": self.provenance, "case_id": CASE,
            "space_id": "angle_space_1", "activity": "parked"})
        self.samples, self.bodies, self.frames = [], [], []
        for i in range(600):
            shared = {"case_id": CASE, "provenance": self.provenance,
                      "native_frame": i+100, "time_s": (i+1)/20}
            self.samples.append({**shared, "sample_index": i, "native_road_id": 1,
                "space_id": "angle_space_1", "ego_heading_deg": 45,
                "ego_speed_mps": 0 if i >= 240 else 1, "activity": "parked"})
            self.bodies.append({**shared, "body_vertices_m": [[0, 0, 0],
                [1, 0, 0], [1, 1, 0], [0, 1, 0]]})
            self.frames.append({**shared, "video_frame": i, "carla_frame": i+100})
        self.persist()

    def persist(self):
        write_rows(self.root / "native_samples.jsonl", self.samples)
        write_rows(self.root / "body_history.jsonl", self.bodies)
        write_rows(self.root / "video_frames.jsonl", self.frames)

    def test_source_bound_positive(self):
        result = measure(self.root, CASE, allow_fixture=True)
        self.assertEqual(result["at_rest_frames"], 360)
        self.assertEqual(result["maximum_absolute_difference_deg"], 0)
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_other_angle_is_measured(self):
        for row in self.samples:
            row["ego_heading_deg"] = 70
        self.persist()
        self.assertEqual(measure(self.root, CASE, allow_fixture=True)
                         ["maximum_absolute_difference_deg"], 25)

    def test_missing_device_rejected(self):
        (self.root / "official_device.json").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: official_device"):
            measure(self.root, CASE, allow_fixture=True)

    def test_missing_curb_rejected(self):
        road = json.loads((self.root / "road_geometry.json").read_text())
        del road["curb_tangent_heading_deg"]
        write(self.root / "road_geometry.json", road)
        with self.assertRaisesRegex(ValueError, "curb or highway-edge"):
            measure(self.root, CASE, allow_fixture=True)

    def test_missing_camera_frame_rejected(self):
        self.frames[300]["native_frame"] += 1
        self.persist()
        with self.assertRaisesRegex(ValueError, "frame join"):
            measure(self.root, CASE, allow_fixture=True)

    def test_forged_original_rejected(self):
        self.samples[0]["provenance"] = "original_native_capture"
        self.persist()
        with self.assertRaisesRegex(ValueError, "provenance"):
            measure(self.root, CASE, allow_fixture=True)

    def test_no_contiguous_rest_rejected(self):
        for i, row in enumerate(self.samples):
            row["ego_speed_mps"] = 0 if i % 2 else 1
        self.persist()
        with self.assertRaisesRegex(ValueError, "Contiguous at-rest"):
            measure(self.root, CASE, allow_fixture=True)


if __name__ == "__main__":
    unittest.main()
