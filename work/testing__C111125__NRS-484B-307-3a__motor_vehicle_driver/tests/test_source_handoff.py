import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))

from dual_green import EvidenceError
from source_handoff import load_handoff
from analysis import build as analyze
from native_publication import publish


class SourceHandoffTests(unittest.TestCase):
    def setUp(self):
        scratch = REPO / ".runtime-work" / "c111125-source-handoff-tests"
        scratch.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        refs = []
        for name in ("map", "route", "signal", "crosswalk", "permission"):
            refs.append(self.write(name + ".json", {"source": name}))
        self.site = {
            "cell_id": "C111125", "actor": "motor_vehicle_driver",
            "original_sources": refs,
            "map_source_path": refs[0]["path"],
            "route_source_path": refs[1]["path"],
            "signal_survey_path": refs[2]["path"],
            "crosswalk_source_path": refs[3]["path"],
            "movement_permission_source_path": refs[4]["path"],
            "official_head_id": "5", "ego_approach_id": "east",
            "facing_relation": True, "arrow_direction": "left",
            "ego_movement": "straight",
            "straight_permission_review": "source_review_pending",
            "ego_route_xy": [[-10, 0], [0, 0], [10, 0]],
            "straight_tolerance_m": .2,
            "intersection_polygon_xy": [[-2, -2], [2, -2], [2, 2], [-2, 2]],
            "adjacent_crosswalk_polygon_xy": [[-4, 3], [4, 3], [4, 5], [-4, 5]],
        }
        frames = []
        for frame in (10, 11, 12):
            image_path = self.root / f"lamp-image-{frame}.png"
            Image.new("RGB", (2, 2), (0, 220, 0)).save(image_path)
            observed = {"path": image_path.name,
                        "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest()}
            lamp = self.write(f"lamp-{frame}.json", {
                "frame": frame, "official_head_id": "5",
                "facing_approach_id": "east",
                "lit_aspects": ["circular_green", "green_left_arrow"],
                "original_observation": observed,
            })
            lawful = self.write(f"lawful-{frame}.json", {
                "frame": frame, "user_id": "2", "review": "unresolved",
            })
            frames.append({"carla_frame": frame, "lamp": lamp,
                           "lawful_use": {"2": lawful}})
        self.handoff = {
            "format": "dual-green-original-source-handoff",
            "case_id": "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__dual_vehicle_present",
            "official_head_id": "5", "facing_approach_id": "east",
            "observer_method": "independent_camera_frame_review",
            "frames": frames,
        }
        (self.root / "handoff.json").write_text(json.dumps(self.handoff) + "\n")

    def write(self, name, obj):
        path = self.root / name
        path.write_text(json.dumps(obj) + "\n")
        return {"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def load(self):
        return load_handoff(self.root / "handoff.json", self.root, self.site,
                            self.handoff["case_id"], expected_frames=3)

    def test_source_callbacks_bind_exact_frame_and_user(self):
        callbacks = self.load()
        self.assertEqual(callbacks["frame_count"], 3)
        self.assertEqual(callbacks["lamp_ref_for_frame"](11),
                         self.handoff["frames"][1]["lamp"])
        self.assertEqual(callbacks["lawful_use_ref_for_frame"](12, "2"),
                         self.handoff["frames"][2]["lawful_use"]["2"])

    def test_missing_original_observation_rejected(self):
        (self.root / "lamp-image-11.png").unlink()
        with self.assertRaisesRegex(EvidenceError, "missing or escaping original source"):
            self.load()

    def test_corrupt_original_image_rejected_even_with_updated_hash(self):
        image = self.root / "lamp-image-11.png"
        image.write_bytes(b"not a PNG")
        lamp_path = self.root / "lamp-11.json"
        lamp = json.loads(lamp_path.read_text())
        lamp["original_observation"]["sha256"] = hashlib.sha256(image.read_bytes()).hexdigest()
        self.handoff["frames"][1]["lamp"] = self.write("lamp-11.json", lamp)
        (self.root / "handoff.json").write_text(json.dumps(self.handoff) + "\n")
        with self.assertRaisesRegex(ValueError, "invalid original lamp observation"):
            self.load()

    def test_changed_arrow_and_frame_gap_rejected(self):
        self.write("lamp-11.json", {
            "frame": 11, "official_head_id": "5", "facing_approach_id": "east",
            "lit_aspects": ["circular_green", "green_right_arrow"],
            "original_observation": self.handoff["frames"][1]["lamp"],
        })
        with self.assertRaisesRegex(EvidenceError, "hash mismatch"):
            self.load()
        self.handoff["frames"][1]["carla_frame"] = 99
        (self.root / "handoff.json").write_text(json.dumps(self.handoff) + "\n")
        with self.assertRaisesRegex(EvidenceError, "frame gap"):
            self.load()

    def test_wrong_case_and_missing_lawful_packet_rejected(self):
        with self.assertRaisesRegex(EvidenceError, "case mismatch"):
            load_handoff(self.root / "handoff.json", self.root, self.site,
                         "wrong-case", expected_frames=3)
        (self.root / "lawful-12.json").unlink()
        with self.assertRaisesRegex(EvidenceError, "missing or escaping original source"):
            self.load()

    def test_synthetic_marker_is_diagnostic_only(self):
        frame = 11
        marker = self.write("synthetic-lamp-11.json", {
            "format": "synthetic-dual-green-lamp-observation",
            "frame": frame, "physical_observation": False,
        })
        lamp_path = self.root / "lamp-11.json"
        lamp = json.loads(lamp_path.read_text())
        lamp["original_observation"] = marker
        self.handoff["frames"][1]["lamp"] = self.write("lamp-11.json", lamp)
        self.handoff["observer_method"] = "synthetic_diagnostic"
        (self.root / "handoff.json").write_text(json.dumps(self.handoff) + "\n")
        with self.assertRaisesRegex(EvidenceError, "observer missing"):
            self.load()
        callbacks = load_handoff(self.root / "handoff.json", self.root, self.site,
                                 self.handoff["case_id"], expected_frames=3,
                                 diagnostic_fixture=True)
        self.assertEqual(callbacks["frame_count"], 3)

    def analysis_fixture(self):
        (self.root / "original-source-handoff.json").write_text(
            json.dumps(self.handoff) + "\n")
        (self.root / "site.json").write_text(json.dumps(self.site) + "\n")
        (self.root / "config.json").write_text(json.dumps({
            "selected_case_id": self.handoff["case_id"]}) + "\n")
        rows = []
        for index, point in enumerate(([-10, 0], [0, 0], [10, 0])):
            frame = index + 10
            lamp = self.handoff["frames"][index]["lamp"]
            lawful = self.handoff["frames"][index]["lawful_use"]["2"]
            rows.append({"frame": frame, "elapsed_seconds": frame * .05,
                         "official_head_id": "5",
                         "facing_approach_id": "east",
                         "aspect_observation_source": lamp["path"],
                         "aspect_observation_sha256": lamp["sha256"],
                         "lit_aspects": ["circular_green", "green_left_arrow"],
                         "ego_xy": point,
                         "other_users": [{"id": "2", "kind": "motor_vehicle", "xy": [0, 0],
                                          "lawful_use_source": lawful["path"],
                                          "lawful_use_sha256": lawful["sha256"]}]})
        (self.root / "original-events.json").write_text(json.dumps(rows) + "\n")

    def test_analysis_binds_four_selected_measurements_to_original_sources(self):
        self.analysis_fixture()
        report = analyze(self.root)
        self.assertEqual(len(report["measurements"]), 4)
        self.assertEqual(report["measurements"]["dual_aspect_observation"]["value"]
                         ["first_exhibition_frame"], 10)
        self.assertEqual(report["measurements"]["vehicle_yield_observation"]["value"]
                         ["intersection_at_exhibition"], ["2"])
        self.assertFalse(report["legal_verdict_claimed"])
        (self.root / "original-source-handoff.json").unlink(missing_ok=True)
        with self.assertRaisesRegex(ValueError, "Missing required source: original-source-handoff.json"):
            analyze(self.root)

    def test_selected_native_result_publishes_saved_channels_without_legal_verdict(self):
        self.analysis_fixture()
        cases = json.loads((ROOT / "proposals" / "cases.json").read_text())["cases"]
        description = next(row["recording_description"] for row in cases if row[
            "case_id"] == self.handoff["case_id"])
        (self.root / "construction.json").write_text(json.dumps({
            "recording_description": description}) + "\n")
        trace = []
        mapping = []
        for index, x in enumerate((-10, 0, 10)):
            frame = index + 10
            time_s = frame * .05
            trace.append({"frame": frame, "time_s": time_s,
                          "position": {"x": x, "y": 0, "z": 0},
                          "heading_deg": 0, "speed_mps": 0})
            mapping.append({"video_frame": index, "carla_frame": frame,
                            "time_s": time_s})
        (self.root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        (self.root / "video_frames.jsonl").write_text("".join(
            json.dumps(row) + "\n" for row in mapping))
        result = publish(self.root, analyze(self.root))
        self.assertEqual(len(result["recording_evidence"]), 9)
        self.assertFalse(result["setup_confirmed"])
        self.assertFalse(result["target_checks"][0]["physical_cause_confirmed"])
        self.assertNotIn("legal_verdict", json.dumps(result))
        self.assertEqual(len((self.root / "original_lamp_pixels.jsonl").read_text().splitlines()), 3)
        with self.assertRaisesRegex(EvidenceError, "already published"):
            publish(self.root, analyze(self.root))


if __name__ == "__main__":
    unittest.main()
