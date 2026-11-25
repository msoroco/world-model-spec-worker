import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_crossing import ASSIGNMENT, CAMERAS, audit_saved_comparison, process_saved


class SavedCrossingTest(unittest.TestCase):
    def setUp(self):
        scratch = Path(__file__).resolve().parents[3] / '.runtime-work/c111329-saved-tests'
        scratch.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.attempt = Path(self.temp.name)
        sources = {}
        for name in ("map", "corner_survey", "authorization", "device_inventory", "exception_review"):
            file = self.attempt / (name + ".txt")
            file.write_text("measured " + name, encoding="utf-8")
            sources[name] = {"path": str(file), "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        self.site = {"sources": sources, "coordinate_frame": "map_xy_m",
                     "corners_clockwise": [[0, 0], [10, 0], [10, 10], [0, 10]],
                     "pedestrian_route": [[0, 0], [5, 5], [10, 10]],
                     "governing_device": {"id": "ped-1", "authority_record_id": "order-1",
                                          "instruction_record_id": "order-1-diagonal",
                                          "placement_record_id": "survey-1", "governs": "pedestrian_diagonal",
                                          "diagonal_authorized": True},
                     "observed_device_ids": ["ped-1"], "exception_484b_290_review": "unresolved"}
        self.case = ASSIGNMENT + "__instruction_changes_during_crossing"
        points = [[0, 0], [3, 3], [5, 5], [7, 7], [10, 10]]
        self.walker = [{"original_frame": 20+i, "elapsed_s": i/20, "walker_id": 7,
                        "center_xy": point} for i, point in enumerate(points)]
        self.device = [{"original_frame": 20+i, "elapsed_s": i/20, "device_id": "ped-1",
                        "source_sha256": sources["device_inventory"]["sha256"],
                        "pedestrian_governance": "diagonal",
                        "instruction": "diagonal_walk" if i < 3 else "diagonal_dont_walk"}
                       for i in range(5)]
        self.cameras = [{"original_frame": 20+i, "elapsed_s": i/20,
                         "cameras": {name: 20+i for name in CAMERAS}} for i in range(5)]
        self.polygon = [[2, 2], [8, 2], [8, 8], [2, 8]]
        self.manifest = {"assignment_id": ASSIGNMENT, "case_id": self.case,
                         "diagnostic": True, "fps": 20, "camera_ids": list(CAMERAS)}
        self.seal()

    def seal(self):
        for name, content in (("site", self.site), ("walker", self.walker),
                              ("device", self.device), ("camera_frames", self.cameras),
                              ("crossing_polygon", self.polygon)):
            file = self.attempt / (name + ".json")
            file.write_text(json.dumps(content), encoding="utf-8")
            self.manifest[name] = {"path": file.name,
                                   "sha256": hashlib.sha256(file.read_bytes()).hexdigest()}
        (self.attempt / "acquisition.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def process(self, **kwargs):
        return process_saved(self.attempt, self.case, self.attempt / "measured.json", **kwargs)

    def test_diagnostic_measurement_and_delivery_rejection(self):
        with self.assertRaisesRegex(ValueError, "diagnostic"):
            self.process()
        result = self.process(allow_diagnostic=True)
        self.assertEqual(result["measurement"]["crossing_frames"], [21, 22, 23])
        self.assertFalse(result["actual_pixels_verified"])
        self.assertEqual(result["legal_conclusion"], "not_assessed")

    def test_source_hash_and_path_rejection(self):
        (self.attempt / "walker.json").write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self.process(allow_diagnostic=True)
        self.seal()
        self.manifest["walker"]["path"] = "../escape.json"
        (self.attempt / "acquisition.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes or is missing"):
            self.process(allow_diagnostic=True)

    def test_frame_time_camera_and_device_source_rejection(self):
        variants = (
            ("walker", lambda: self.walker[2].update(original_frame=31), "frame gap"),
            ("walker", lambda: self.walker[2].update(elapsed_s=1.0), "20 Hz"),
            ("camera", lambda: self.cameras[2]["cameras"].update(overview=31), "camera original-frame"),
            ("device", lambda: self.device[2].update(source_sha256="wrong"), "inventoried source"),
        )
        for _, mutate, expected in variants:
            with self.subTest(expected=expected):
                previous = copy.deepcopy((self.walker, self.device, self.cameras))
                mutate()
                self.seal()
                with self.assertRaisesRegex(ValueError, expected):
                    self.process(allow_diagnostic=True)
                self.walker, self.device, self.cameras = previous

    def test_exact_instruction_and_case_identity(self):
        self.device = [{**row, "instruction": "diagonal_walk"} for row in self.device]
        self.seal()
        with self.assertRaisesRegex(ValueError, "phase-change"):
            self.process(allow_diagnostic=True)
        self.case = ASSIGNMENT + "__prohibitive_whole_crossing"
        self.manifest["case_id"] = self.case
        self.seal()
        with self.assertRaisesRegex(ValueError, "prohibitive"):
            self.process(allow_diagnostic=True)
        self.case = ASSIGNMENT + "__unassigned"
        with self.assertRaisesRegex(ValueError, "unassigned"):
            self.process(allow_diagnostic=True)

    def test_saved_comparison_isolation(self):
        change = self.process(allow_diagnostic=True)
        self.case = ASSIGNMENT + "__permissive_whole_crossing"
        self.manifest["case_id"] = self.case
        self.device = [{**row, "instruction": "diagonal_walk"} for row in self.device]
        self.seal()
        permissive = self.process(allow_diagnostic=True)
        with self.assertRaisesRegex(ValueError, "diagnostic"):
            audit_saved_comparison(permissive, change)
        self.assertTrue(audit_saved_comparison(permissive, change,
                                              allow_diagnostic=True)["comparison_verified"])
        drift = copy.deepcopy(change)
        drift["source_sha256"]["site"] = "different-site"
        with self.assertRaisesRegex(ValueError, "site changed"):
            audit_saved_comparison(permissive, drift, allow_diagnostic=True)
        drift = copy.deepcopy(change)
        drift["measurement"]["crossing_frames"] = [21, 22]
        with self.assertRaisesRegex(ValueError, "crossing_frames"):
            audit_saved_comparison(permissive, drift, allow_diagnostic=True)
        drift = copy.deepcopy(change)
        drift["camera_ids"] = ["front"]
        with self.assertRaisesRegex(ValueError, "camera_ids"):
            audit_saved_comparison(permissive, drift, allow_diagnostic=True)


if __name__ == "__main__":
    unittest.main()
