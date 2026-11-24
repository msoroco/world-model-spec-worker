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


if __name__ == "__main__":
    unittest.main()
