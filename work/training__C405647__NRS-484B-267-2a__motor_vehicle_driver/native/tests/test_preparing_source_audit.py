import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preparing_source_audit import BASE, BRANCHES, VIEWS, audit, audit_structure
from preparing_finalize import finalize, measure


class PreparingSourceAuditTest(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(__file__).resolve().parents[4] / ".runtime-work"
        self.scratch.mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=self.scratch)
        self.addCleanup(self.temporary.cleanup)
        self.attempt = Path(self.temporary.name)

    def fixture(self, branch):
        case = BASE + branch
        mapping = []
        observations = []
        for index in range(600):
            frame = 1000 + index
            mapping.append({"video_frame": index, "native_frame": frame,
                            "time_s": index / 20})
            observations.append({"video_frame": index, "native_frame": frame,
                                 "time_s": index / 20, "case_id": case,
                                 "source_kind": "original_native_observation",
                                 "camera_frames": {view: frame for view in VIEWS},
                                 "ego": {"actor_id": 1,
                                         "road_x_m": -150 + min(index, 200) * 14 / 20
                                         + max(index - 200, 0) * 7 / 20,
                                         "speed_mps": 14 if index < 200 else 7},
                                 "qualifying_vehicle": {"actor_id": 42,
                                                        "road_x_m": 70 + (
                                                            max(index - 120, 0) / 20
                                                            if branch == BRANCHES[0] else 0),
                                                        "speed_mps": 1 if branch == BRANCHES[0]
                                                        and index >= 120 else 0},
                                 "hand_signal_driver_actor_id": 43
                                 if branch == BRANCHES[1] and index >= 120 else None,
                                 "hand_signal_pose_requested": branch == BRANCHES[1]
                                 and index >= 120,
                                 branch: index >= 120})
        (self.attempt / "video_frames.jsonl").write_text(
            "\n".join(json.dumps(row) for row in mapping) + "\n")
        (self.attempt / "preparing_observations.jsonl").write_text(
            "\n".join(json.dumps(row) for row in observations) + "\n")
        for name in ("primary", *VIEWS):
            (self.attempt / (name + ".mkv")).write_bytes(b"synthetic test bytes " + name.encode())
        hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                  for path in self.attempt.iterdir()}
        review = {"case_id": case, "activation_branch": branch,
                  "source_kind": "original_native_observation", "source_sha256": hashes,
                  "pixel_review": {"source_video_sha256": hashes["primary.mkv"],
                                   "reviewer": "fixture-reviewer", "review_method": "fixture",
                                   "branch": branch, "visible": True,
                                   "vehicle_actor_id": 42, "first_visible_frame": 120,
                                   "driver_actor_id": 43, "hand_signal_type": "left",
                                   "hand_signal_actor_source_id": "source:driver"},
                  "source_witness": {
                      "subject_approach_source_id": "source:approach",
                      "authorized_vehicle_source_id": "source:vehicle",
                      "vehicle_kind": "authorized_emergency_vehicle",
                      "flashing_equipment_source_id": "source:equipment",
                      "flashing_pixel_source_id": "source:lamp-pixels",
                      "flashing_qualification_source_id": "source:lamp-review",
                      "officer_direction_source_id": "source:officer",
                      "road_context_source_id": "source:road",
                      "weather_context_source_id": "source:weather",
                      "officer_directed": False}}
        return review

    def test_both_exact_branches_structural(self):
        for branch in BRANCHES:
            with self.subTest(branch=branch):
                review = self.fixture(branch)
                result = audit_structure(self.attempt, review)
                self.assertEqual(result["first_visible_frame"], 120)
                self.assertGreater(result["first_reach_frame"], 120)
                self.assertGreater(result["initial_approach_speed_mps"],
                                   result["last_approach_speed_mps"])
                self.assertFalse(result["physical_completion_claimed"])
                with self.assertRaisesRegex(ValueError, "Missing or escaping source"):
                    audit(self.attempt, review)

    def test_changed_original_rejected(self):
        review = self.fixture(BRANCHES[0])
        with (self.attempt / "preparing_observations.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "Original source hash changed"):
            audit_structure(self.attempt, review)

    def test_missing_pixel_and_actor_review_rejected(self):
        review = self.fixture(BRANCHES[1])
        review["pixel_review"]["hand_signal_actor_source_id"] = None
        with self.assertRaisesRegex(ValueError, "driver hand signal"):
            audit_structure(self.attempt, review)

    def test_changed_frame_join_rejected(self):
        review = self.fixture(BRANCHES[0])
        path = self.attempt / "video_frames.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[120]["native_frame"] += 1
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        review["source_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "frame and time join"):
            audit_structure(self.attempt, review)

    def test_missing_original_motion_rejected(self):
        review = self.fixture(BRANCHES[0])
        path = self.attempt / "preparing_observations.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[250]["ego"].pop("speed_mps")
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        review["source_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "motion measurement missing"):
            audit_structure(self.attempt, review)

    def test_hand_signal_actor_join_rejected(self):
        review = self.fixture(BRANCHES[1])
        path = self.attempt / "preparing_observations.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[120]["hand_signal_driver_actor_id"] = 99
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        review["source_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "another driver"):
            audit_structure(self.attempt, review)

    def test_already_moving_before_visible_indication_rejected(self):
        review = self.fixture(BRANCHES[0])
        path = self.attempt / "preparing_observations.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[60]["qualifying_vehicle"]["speed_mps"] = 3
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
        review["source_sha256"][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, "already moving"):
            audit_structure(self.attempt, review)

    def test_recorded_only_measurement_for_both_branches(self):
        for branch in BRANCHES:
            with self.subTest(branch=branch):
                review = self.fixture(branch)
                states = [json.loads(line) for line in
                          (self.attempt / "preparing_observations.jsonl").read_text().splitlines()]
                mapping = [json.loads(line) for line in
                           (self.attempt / "video_frames.jsonl").read_text().splitlines()]
                value = measure(states, mapping, review["case_id"])
                self.assertEqual(value["first_branch_source_frame"], 120)
                self.assertFalse(value["visible_to_subject_confirmed"])
                self.assertLess(value["last_approach_speed_mps"],
                                value["initial_approach_speed_mps"])
                self.assertFalse(value["reasonable_and_proper_legally_determined"])

    def test_recorded_only_missing_frame_rejected(self):
        review = self.fixture(BRANCHES[0])
        states = [json.loads(line) for line in
                  (self.attempt / "preparing_observations.jsonl").read_text().splitlines()]
        mapping = [json.loads(line) for line in
                   (self.attempt / "video_frames.jsonl").read_text().splitlines()]
        mapping[120]["native_frame"] += 1
        with self.assertRaisesRegex(ValueError, "frame join differs"):
            measure(states, mapping, review["case_id"])

    def test_recorded_only_finalizer_preserves_sources(self):
        review = self.fixture(BRANCHES[0])
        (self.attempt / "trace.jsonl").write_text("{\"time_s\": 0}\n")
        (self.attempt / "capture").mkdir()
        (self.attempt / "capture/manifest.json").write_text("{}\n")
        (self.attempt / "acquisition-provenance.json").write_text(
            json.dumps({"diagnostic_fixture": True, "provenance_kind": "synthetic_fixture"}) + "\n")
        (self.attempt / "config.json").write_text(json.dumps({"case_id": review["case_id"]}) + "\n")
        (self.attempt / "construction.json").write_text(json.dumps({
            "case_id": review["case_id"], "recording_description": {"channels": []}}) + "\n")
        originals = {path.relative_to(self.attempt).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in self.attempt.rglob("*") if path.is_file()}
        repo = Path(__file__).resolve().parents[4]
        os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(repo / ".runtime-work" / "c405647")
        sys.path.insert(0, str(repo / "runtime" / "scenario_pipeline"))
        output = self.attempt / "preparing-analysis.json"
        report = finalize(self.attempt, output)
        self.assertTrue(report["fixture_only"])
        self.assertFalse(json.loads((self.attempt / "result.json").read_text())["setup_confirmed"])
        self.assertEqual(originals, {path.relative_to(self.attempt).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in self.attempt.rglob("*") if path.is_file()
                                     and path.relative_to(self.attempt).as_posix() in originals})
        with self.assertRaisesRegex(ValueError, "fresh attempt"):
            finalize(self.attempt, self.attempt / "another.json")


if __name__ == "__main__":
    unittest.main()
