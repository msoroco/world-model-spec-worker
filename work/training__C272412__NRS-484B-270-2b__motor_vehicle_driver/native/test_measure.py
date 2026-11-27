"""Synthetic source-shaped tests for the original-only saved reducer."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from measure import measure, surface_gap
from scene import FRAMES, HZ, open_drive, target


def body(actor_id, blueprint, x, y, half_length, half_width):
    corners = [[x - half_length, y - half_width], [x - half_length, y + half_width],
               [x + half_length, y - half_width], [x + half_length, y + half_width]]
    return {"actor_id": actor_id, "blueprint_id": blueprint,
            "center_xy_m": [x, y], "body_xy_m": corners}


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def fixture(root, suffix="witness_1"):
    source = {key: "reviewed original source" for key in (
        "source_path", "device_blueprint_source", "device_subtype_source",
        "scooter_classification_source", "scooter_handlebars_source",
        "scooter_electric_motor_source", "scooter_riding_design_source",
        "scooter_mass_source", "scooter_motor_max_speed_source",
        "rider_identity_source")}
    source.update(device_blueprint="vehicle.surveyed_scooter", device_subtype="electric_scooter",
                  scooter_rider_excluded_mass_lb=30, scooter_motor_only_max_mph=15)
    survey = root / "original-context-survey.json"
    survey.write_text(json.dumps(source) + "\n")
    attempt = root / "attempt"
    attempt.mkdir()
    (attempt / "road.xodr").write_text(open_drive(suffix == "exception_1_2"))
    (attempt / "pass-context.json").write_text(json.dumps({
        "statutory_subject": "electric_scooter", "source_kind": "generated_software_diagnostic",
        "scooter_actor_id": 22,
        "scooter_blueprint_id": source["device_blueprint"],
        "survey_path": str(survey), "survey_sha256": hashlib.sha256(survey.read_bytes()).hexdigest(),
        "same_direction_lane_count_authored": 1,
        "center_marking_authored": "solid" if suffix == "exception_1_2" else "broken"}) + "\n")
    poses, traces, frames, captures = [], [], [], []
    for index in range(FRAMES):
        plan = target(suffix, index)
        native = 1000 + index
        time_s = index / HZ
        poses.append({"frame": native, "video_frame": index, "time_s": time_s,
                      "ego": body(11, "vehicle.tesla.model3", plan.ego_x_m, plan.ego_y_m, 2.2, .9),
                      "scooter": body(22, source["device_blueprint"], plan.scooter_x_m,
                                      plan.scooter_y_m, .75, .35),
                      "authored_center_marking": "solid" if suffix == "exception_1_2" else "broken"})
        traces.append({"frame": native, "time_s": time_s})
        frames.append({"carla_frame": native, "time_s": time_s,
                       "camera_native_frames": {name: native for name in
                                                ("overview", "approach", "reference_corner", "driver_reference")}})
        captures.append({"original_frame": native})
    for name, rows in (("participant-poses.jsonl", poses), ("trace.jsonl", traces),
                       ("video_frames.jsonl", frames), ("capture/evidence.jsonl", captures)):
        write_jsonl(attempt / name, rows)
    return attempt


class MeasureTests(unittest.TestCase):
    def test_polygon_surface_gap(self):
        a = body(1, "a", 0, 0, 1, 1)
        b = body(2, "b", 0, 2, 1, .5)
        self.assertAlmostEqual(surface_gap(a, b), .5)
        self.assertEqual(surface_gap(a, body(2, "b", 0, 0, .5, .5)), 0)

    def test_full_source_join_and_mutations(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temp:
            attempt = fixture(Path(temp))
            facts = measure(attempt)
            self.assertEqual(facts["abreast_frame_count"] > 0, True)
            self.assertAlmostEqual(facts["minimum_body_surface_gap_m"], 1.2)
            self.assertFalse(facts["safely_clear_legally_judged"])
            source = attempt / "video_frames.jsonl"
            original = source.read_text()
            source.write_text(original.replace('"driver_reference": 1200', '"driver_reference": 9999', 1))
            with self.assertRaisesRegex(ValueError, "four-camera"):
                measure(attempt)
            source.write_text(original)
            survey = Path(json.loads((attempt / "pass-context.json").read_text())["survey_path"])
            survey.write_text(survey.read_text().replace("electric_scooter", "bicycle"))
            with self.assertRaisesRegex(ValueError, "survey source missing or changed"):
                measure(attempt)

    def test_early_return_is_measured_not_fabricated_source_rejection(self):
        with tempfile.TemporaryDirectory(dir=os.environ["TMPDIR"]) as temp:
            attempt = fixture(Path(temp), "ordering_1")
            facts = measure(attempt)
            self.assertFalse(facts["return_after_last_abreast_sample"])
            self.assertFalse(facts["safely_clear_legally_judged"])


if __name__ == "__main__":
    unittest.main()
