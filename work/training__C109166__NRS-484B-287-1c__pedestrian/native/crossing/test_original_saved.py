"""Source-join mutations for original crossing measurements."""

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from original_capture import CAMERAS
from original_saved import measure

ASSIGNMENT = "training__C109166__NRS-484B-287-1c__pedestrian"
PIXEL_SHA = hashlib.sha256(b"source pixels").hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False) + "\n")


def build(root, case):
    config = {"assignment_id": ASSIGNMENT, "case_id": ASSIGNMENT + "__" + case,
              "requested_crossing_location": case, "candidate_id": "primary",
              "rate_hz": 20, "duration_s": 30, "frames": 600,
              "camera_dimensions": {name: [width, height] for name, width, height in CAMERAS},
              "detail_camera_height_m": 5.0}
    write(root / "config.json", config)
    write(root / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    survey = {"review_status": "synthetic_diagnostic",
              "controls": [{"native_actor_id": 201}, {"native_actor_id": 202}],
              "roadway_boundary": {"entry_y_m": -4.0},
              "marked_crosswalk": {"polygon_xy_m": [[38, -5], [42, -5], [42, 5], [38, 5]]}}
    write(root / "native-survey.json", survey)
    media = {}
    (root / "native-survey-media").mkdir()
    for name in ("map.txt", "light-1.txt", "light-2.txt", "marking.txt"):
        path = root / "native-survey-media" / name
        path.write_text(name)
        media[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(root / "native-survey-provenance.json", {
        "copied_sha256": hashlib.sha256((root / "native-survey.json").read_bytes()).hexdigest(),
        "copied_media": media})
    write(root / "native-capture-report.json", {
        "case_id": config["case_id"], "frames": 600, "expected_frames": 600,
        "error": None, "restoration": {"restored": True},
        "survey_sha256": hashlib.sha256((root / "native-survey.json").read_bytes()).hexdigest()})
    files = {name: (root / name).open("w") for name in
             ("video_frames.jsonl", "trace.jsonl", "pedestrian-original.jsonl",
              "controls-original.jsonl", "camera-sources.jsonl")}
    x = 40.0 if case == "marked_crosswalk" else 60.0
    previous_y = None
    try:
        for index in range(600):
            frame = 1000 + index
            time = (index + 1) / 20
            y = -10 + index / 599 * 20
            entered = previous_y is not None and previous_y < -4 <= y
            previous_y = y
            identities = {"video_frame": index, "carla_frame": frame,
                          "native_frame": frame, "time_s": time,
                          "source_rgb_sha256": {name: PIXEL_SHA for name, _, _ in CAMERAS}}
            person = {"native_frame": frame, "time_s": time,
                      "center_xy_m": [x, y],
                      "footprint_xy_m": [[x - 0.2, y - 0.2], [x + 0.2, y - 0.2],
                                         [x + 0.2, y + 0.2], [x - 0.2, y + 0.2]],
                      "roadway_entry_observed": entered}
            devices = {"native_frame": frame, "time_s": time,
                       "controls": [{"native_actor_id": ident, "native_state": "Green",
                                     "operating_observed": True} for ident in (201, 202)]}
            for name, row in (("video_frames.jsonl", identities), ("trace.jsonl", {"frame": frame}),
                              ("pedestrian-original.jsonl", person),
                              ("controls-original.jsonl", devices)):
                files[name].write(json.dumps(row, allow_nan=False) + "\n")
            for name, width, height in CAMERAS:
                files["camera-sources.jsonl"].write(json.dumps({
                    "camera": name, "video_frame": index, "native_frame": frame,
                    "time_s": time, "width": width, "height": height,
                    "rgb_sha256": PIXEL_SHA}) + "\n")
    finally:
        for stream in files.values():
            stream.close()
    for name, _, _ in CAMERAS:
        (root / (name + ".mkv")).write_bytes(b"synthetic camera placeholder")


class SavedSourceChecks(unittest.TestCase):
    def test_both_crossings_and_source_rejections(self):
        for case, expected in (("marked_crosswalk", True), ("unmarked_midblock", False)):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                build(root, case)
                result = measure(root, decode_video=False)
                self.assertEqual(result["entry"]["within_marked_crosswalk_polygon"], expected)
                self.assertTrue(result["entry"]["both_controls_operating"])
                self.assertIsNone(result["legal_verdict"])
                source = root / "controls-original.jsonl"
                original = source.read_text()
                rows = original.splitlines()
                entry = result["entry"]["video_frame"]
                changed = json.loads(rows[entry])
                changed["controls"][1]["operating_observed"] = False
                rows[entry] = json.dumps(changed)
                source.write_text("\n".join(rows) + "\n")
                with self.assertRaisesRegex(ValueError, "not operating"):
                    measure(root, decode_video=False)
                source.write_text(original)
                (root / "reference_corner.mkv").unlink()
                with self.assertRaisesRegex(ValueError, "Missing required source"):
                    measure(root, decode_video=False)

    def test_frame_map_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            build(root, "marked_crosswalk")
            path = root / "video_frames.jsonl"
            lines = path.read_text().splitlines()
            changed = json.loads(lines[100])
            changed["carla_frame"] += 1
            lines[100] = json.dumps(changed)
            path.write_text("\n".join(lines) + "\n")
            with self.assertRaisesRegex(ValueError, "FrameMap join"):
                measure(root, decode_video=False)


if __name__ == "__main__":
    unittest.main()
