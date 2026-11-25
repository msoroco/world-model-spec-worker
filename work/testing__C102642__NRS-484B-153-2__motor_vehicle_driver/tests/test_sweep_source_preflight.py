import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sweep_source_preflight import _polygon_gap, validate_sweep_sources
from test_site_contract import packet


def write_source(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SweepSourcePreflightTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        folder = Path(self.temp.name)
        self.survey_path = folder / "survey.json"
        self.clearance_path = folder / "clearance.json"
        self.survey = packet()
        self.source_paths = {}
        refs = []
        for level, gap in (("below", 0.2), ("inside", 0.6), ("above", 1.2)):
            source_path = folder / (level + ".json")
            self.source_paths[level] = source_path
            case_id = ("testing__C102642__NRS-484B-153-2__motor_vehicle_driver__"
                       + {"below": "open_near_overlap", "inside": "open_near_clear",
                          "above": "open_far_side"}[level])
            sample = {
                "source_kind": "native_original_clearance_frame",
                "map_sha256": self.survey["map_sha256"],
                "loading_site_id": self.survey["loading_site_id"],
                "case_id": case_id,
                "source_observation_id": "original-" + level,
                "frame_id": 240, "door_open": True, "passing_speed_mps": 6.0,
                "door_vertices_xy": [[0, 0], [1, 0], [1, 1], [0, 1]],
                "passing_body_vertices_xy": [[1 + gap, 0], [2 + gap, 0],
                                             [2 + gap, 1], [1 + gap, 1]],
            }
            refs.append({"level": level, "case_id": case_id,
                         "path": source_path.name,
                         "sha256": write_source(source_path, sample)})
        self.clearance = {
            "source_kind": "original_surveyed_clearance_range",
            "map_sha256": self.survey["map_sha256"],
            "loading_site_id": self.survey["loading_site_id"],
            "source_observation_id": "reviewed-measurement-1",
            "measurement_method": "Original surveyed body and door vertices in world XY",
            "source_refs": refs,
            "door_body_gap_levels_m": {"below": 0.2, "inside": 0.6, "above": 1.2},
        }

    def verify(self):
        survey_sha = write_source(self.survey_path, self.survey)
        clearance_sha = write_source(self.clearance_path, self.clearance)
        return validate_sweep_sources(self.survey_path, survey_sha,
                                      self.clearance_path, clearance_sha)

    def test_five_cases_and_unresolved_legal_judgment(self):
        proof = self.verify()
        self.assertEqual(len(proof["selected_cases"]), 5)
        self.assertEqual(proof["legal_interference"], "unresolved_judgment")
        self.assertAlmostEqual(proof["levels_m"]["inside"], 0.6)
        self.assertEqual(proof["source_frames"]["inside"]["frame_id"], 240)

    def test_wrong_site_or_source_origin_rejected(self):
        self.clearance["loading_site_id"] = "another-site"
        with self.assertRaisesRegex(ValueError, "does not join"):
            self.verify()
        self.clearance["loading_site_id"] = self.survey["loading_site_id"]
        self.clearance["source_kind"] = "diagnostic_fixture"
        with self.assertRaisesRegex(ValueError, "original surveyed"):
            self.verify()

    def test_missing_or_unordered_levels_rejected(self):
        del self.clearance["door_body_gap_levels_m"]["inside"]
        with self.assertRaisesRegex(ValueError, "three declared"):
            self.verify()
        self.clearance["door_body_gap_levels_m"] = {
            "below": 0.5, "inside": 0.5, "above": 1.0}
        with self.assertRaisesRegex(ValueError, "differs from original vertices"):
            self.verify()

    def test_missing_stale_or_non_native_frame_rejected(self):
        self.clearance["source_refs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            self.verify()
        self.clearance["source_refs"][0]["sha256"] = hashlib.sha256(
            self.source_paths["below"].read_bytes()).hexdigest()
        sample = json.loads(self.source_paths["below"].read_text())
        sample["source_kind"] = "diagnostic_fixture"
        self.clearance["source_refs"][0]["sha256"] = write_source(
            self.source_paths["below"], sample)
        with self.assertRaisesRegex(ValueError, "original Native"):
            self.verify()

    def test_declared_gap_cannot_be_substituted_for_vertices(self):
        self.clearance["door_body_gap_levels_m"]["inside"] = 0.9
        with self.assertRaisesRegex(ValueError, "differs from original vertices"):
            self.verify()

    def test_frame_must_join_exact_selected_case_and_observation(self):
        sample = json.loads(self.source_paths["below"].read_text())
        sample["case_id"] = sample["case_id"].replace("C102642", "C228817")
        self.clearance["source_refs"][0]["sha256"] = write_source(
            self.source_paths["below"], sample)
        with self.assertRaisesRegex(ValueError, "assignment case"):
            self.verify()
        sample["case_id"] = self.clearance["source_refs"][0]["case_id"]
        sample["source_observation_id"] = ""
        self.clearance["source_refs"][0]["sha256"] = write_source(
            self.source_paths["below"], sample)
        with self.assertRaisesRegex(ValueError, "observation identity"):
            self.verify()

    def test_unknown_assignment_case_is_not_a_selected_case(self):
        sample = json.loads(self.source_paths["below"].read_text())
        sample["case_id"] = ("testing__C102642__NRS-484B-153-2__"
                             "motor_vehicle_driver__unselected")
        self.clearance["source_refs"][0]["case_id"] = sample["case_id"]
        self.clearance["source_refs"][0]["sha256"] = write_source(
            self.source_paths["below"], sample)
        with self.assertRaisesRegex(ValueError, "assignment case"):
            self.verify()

    def test_reused_frame_is_not_three_independent_levels(self):
        self.clearance["source_refs"][1]["path"] = self.clearance["source_refs"][0]["path"]
        self.clearance["source_refs"][1]["sha256"] = self.clearance["source_refs"][0]["sha256"]
        with self.assertRaisesRegex(ValueError, "distinct original frames"):
            self.verify()

    def test_contained_body_has_zero_boundary_clearance(self):
        self.assertEqual(_polygon_gap(
            [[0, 0], [3, 0], [3, 3], [0, 3]],
            [[1, 1], [2, 1], [2, 2], [1, 2]]), 0.0)

    def test_unclosed_outline_includes_last_to_first_edge(self):
        door = [[0, 0], [1, 0], [1, 1], [0, 1]]
        passing_body = [[-2, 0.4], [-1, 0.4], [-1, 0.6], [-2, 0.6]]
        self.assertAlmostEqual(_polygon_gap(door, passing_body), 1.0)
        self.assertAlmostEqual(_polygon_gap(door + [door[0]], passing_body), 1.0)

    def test_stale_clearance_hash_rejected(self):
        survey_sha = write_source(self.survey_path, self.survey)
        write_source(self.clearance_path, self.clearance)
        with self.assertRaisesRegex(ValueError, "source hash mismatch"):
            validate_sweep_sources(self.survey_path, survey_sha,
                                   self.clearance_path, "0" * 64)


if __name__ == "__main__":
    unittest.main()
