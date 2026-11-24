import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "saved_encounter.py"
module_spec = importlib.util.spec_from_file_location("saved_encounter", SOURCE)
saved = importlib.util.module_from_spec(module_spec)
sys.modules[module_spec.name] = saved
module_spec.loader.exec_module(saved)


class SavedEncounterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.rows = [
            {"frame": 100 + i, "time_s": i * 0.05, "person_actor_id": 5,
             "driver_speed_mps": 0 if i in (2, 3) else 2,
             "body_gap_m": 10 - i, "person_in_path": True,
             "person_clear": i >= 4, "contact": False, "precaution": i >= 4}
            for i in range(6)
        ]
        self.write("history.jsonl", "".join(json.dumps(r) + "\n" for r in self.rows))
        self.write("attestation.json", json.dumps({
            "person_actor_id": 5, "source_sha256": "a" * 64,
            "basis": "partially_blind", "issuer": "independent source fixture"}))
        self.write("cue.json", json.dumps({
            "person_actor_id": 5, "source_sha256": "b" * 64,
            "cue": "white_cane", "observation": "actually_carried",
            "observer_source": "original-camera fixture"}))
        self.manifest = {
            "assignment_id": saved.ASSIGNMENT_ID,
            "case_id": "white_full_stop_wait", "original_frame_count": 6,
            "original_history": self.entry("history.jsonl"),
            "blindness_attestation": self.entry("attestation.json"),
            "carried_cue": self.entry("cue.json"),
        }

    def write(self, name, content):
        (self.root / name).write_text(content, encoding="utf-8")

    def entry(self, name):
        return {"path": name, "sha256": hashlib.sha256((self.root / name).read_bytes()).hexdigest()}

    def process(self):
        self.write("manifest.json", json.dumps(self.manifest))
        return saved.process(self.root / "manifest.json", self.root / "measurement.json")

    def test_source_bound_saved_measurement(self):
        result = self.process()
        self.assertEqual(result["first_stop_frame"], 102)
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(result["source_bindings"]["original_history"], self.manifest["original_history"]["sha256"])
        self.assertEqual(json.loads((self.root / "measurement.json").read_text())["first_proceed_frame"], 104)

    def test_existing_saved_measurement_is_preserved(self):
        self.process()
        original = (self.root / "measurement.json").read_bytes()
        with self.assertRaisesRegex(ValueError, "preserve prior saved encounter output"):
            self.process()
        self.assertEqual((self.root / "measurement.json").read_bytes(), original)

    def test_tampered_source_rejected_before_output(self):
        self.write("manifest.json", json.dumps(self.manifest))
        self.write("cue.json", (self.root / "cue.json").read_text() + " ")
        with self.assertRaisesRegex(ValueError, "carried cue source hash mismatch"):
            saved.process(self.root / "manifest.json", self.root / "measurement.json")
        self.assertFalse((self.root / "measurement.json").exists())

    def test_missing_independent_blindness_and_carried_cue_rejected(self):
        self.write("attestation.json", json.dumps({"person_actor_id": 5, "source_sha256": "a" * 64}))
        self.manifest["blindness_attestation"] = self.entry("attestation.json")
        with self.assertRaisesRegex(ValueError, "basis and issuer"):
            self.process()
        self.write("attestation.json", json.dumps({"person_actor_id": 5, "source_sha256": "a" * 64,
                                                   "basis": "wholly_blind", "issuer": "fixture"}))
        self.manifest["blindness_attestation"] = self.entry("attestation.json")
        self.write("cue.json", json.dumps({"person_actor_id": 5, "source_sha256": "b" * 64,
                                           "cue": "white_cane"}))
        self.manifest["carried_cue"] = self.entry("cue.json")
        with self.assertRaisesRegex(ValueError, "observed carried cue"):
            self.process()

    def test_incomplete_history_and_path_escape_rejected(self):
        self.manifest["original_frame_count"] = 5
        with self.assertRaisesRegex(ValueError, "frame count"):
            self.process()
        self.manifest["original_frame_count"] = 6
        self.manifest["original_history"]["path"] = "../history.jsonl"
        with self.assertRaisesRegex(ValueError, "missing or escaping"):
            self.process()

    def test_reviewed_source_custody_positive_and_changed_map_rejection(self):
        original_att = {"reviewed_fact": "diagnostic blindness basis"}
        original_cue = {"reviewed_fact": "diagnostic carried cane"}
        self.write("original-att.json", json.dumps(original_att) + "\n")
        self.write("original-cue.json", json.dumps(original_cue) + "\n")
        att_source, cue_source = self.entry("original-att.json"), self.entry("original-cue.json")
        self.write("attestation.json", json.dumps({
            "person_actor_id": 5, "source_sha256": att_source["sha256"],
            "basis": "partially_blind", "issuer": "diagnostic fixture",
            "original_source": att_source}) + "\n")
        self.write("cue.json", json.dumps({
            "person_actor_id": 5, "source_sha256": cue_source["sha256"],
            "cue": "white_cane", "observation": "actually_carried",
            "observer_source": "diagnostic fixture", "original_source": cue_source}) + "\n")
        self.manifest["blindness_attestation"] = self.entry("attestation.json")
        self.manifest["carried_cue"] = self.entry("cue.json")
        route = [{"map_id": "FixtureTown", "x": x, "y": 0, "road_id": 1, "lane_id": 1}
                 for x in (0, 10)]
        self.write("map.json", json.dumps({
            "reviewed_from": "original_native_map", "reviewer": "diagnostic fixture",
            "map_id": "FixtureTown", "route_waypoints": route,
            "pedestrian_pose": {"map_id": "FixtureTown", "x": 10, "y": 2, "ground_z": 0},
            "driver_actor_id": 4, "pedestrian_actor_id": 5}) + "\n")
        self.write("packet.json", json.dumps({
            "assignment_id": saved.ASSIGNMENT_ID, "case_id": "white_full_stop_wait",
            "reviewed_map_route": self.entry("map.json"),
            "blindness_attestation": self.manifest["blindness_attestation"],
            "carried_cue": self.manifest["carried_cue"]}) + "\n")
        plan = saved.reviewed_sources.prepare(self.root / "packet.json")
        self.manifest["reviewed_source_packet"] = self.entry("packet.json")
        self.manifest["reviewed_source_bindings"] = plan["reviewed_source_bindings"]
        self.manifest["reviewed_map_id"] = plan["map_id"]
        self.write("manifest.json", json.dumps(self.manifest) + "\n")
        result = saved.process(self.root / "manifest.json", self.root / "measurement.json",
                               require_reviewed=True)
        self.assertEqual(result["reviewed_map_id"], "FixtureTown")
        (self.root / "measurement.json").unlink()
        self.write("map.json", '{"changed": true}\n')
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            saved.process(self.root / "manifest.json", self.root / "measurement.json",
                          require_reviewed=True)
        self.assertFalse((self.root / "measurement.json").exists())


if __name__ == "__main__":
    unittest.main()
