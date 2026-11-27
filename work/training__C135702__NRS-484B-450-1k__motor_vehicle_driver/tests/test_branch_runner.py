"""Original-shaped context adapter checks for the police source branch runner."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "native"))
from branch_runner import PREFIX, reviewed_context


class PoliceSourceRunnerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="c135702-police-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def write_record(self, name, values):
        path = self.root / (name + ".json")
        path.write_text(json.dumps({"source_kind": name,
                                    "original_record_id": "diagnostic-" + name, **values}) + "\n")
        return {"kind": name, "provenance": "reviewed_original_source",
                "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def context(self, suffix):
        present = suffix == "police_present"
        activity = self.write_record("operator_activity", {"requested_activity": "park"})
        sources = {}
        for name in ("traffic_conflict", "law_direction", "police_direction", "traffic_device"):
            values = {"requested_exception": name if present and name == "police_direction" else None,
                      "event_window": "diagnostic interval", "scene_scope": "diagnostic narrow road"}
            if name == "police_direction":
                values["original_instruction"] = "diagnostic instruction record"
            if name == "traffic_device":
                values["original_instruction"] = "diagnostic device record"
            if name == "law_direction":
                values["law_citation"] = "diagnostic law citation"
            if name == "traffic_conflict":
                values["traffic_source_refs"] = ["diagnostic traffic source"]
            sources[name] = self.write_record(name, values)
        flags = {name: name == "police_direction" and present for name in sources}
        context = {"case_id": PREFIX + suffix, "source_kind": "reviewed_branch_context",
                   "activity_request": "park",
                   "exception_request": "police_direction" if present else None,
                   "activity_source": activity, "exception_sources": sources,
                   "source_records": {"operator_activity": activity, **sources},
                   "exceptions": flags,
                   "exception_source": {name + "_reviewed": True for name in sources}}
        path = self.root / "context.json"
        path.write_text(json.dumps(context) + "\n")
        return path

    def test_absent_and_present_original_shaped_source_protocol(self):
        for suffix in ("police_absent", "police_present"):
            with self.subTest(suffix=suffix):
                path = self.context(suffix)
                result, digest = reviewed_context(path, PREFIX + suffix)
                self.assertEqual(result["exceptions"]["police_direction"], suffix == "police_present")
                self.assertEqual(digest, hashlib.sha256(path.read_bytes()).hexdigest())

    def test_unmatched_flag_rejected(self):
        path = self.context("police_present")
        value = json.loads(path.read_text())
        value["exceptions"]["police_direction"] = False
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaisesRegex(ValueError, "flags differ"):
            reviewed_context(path, PREFIX + "police_present")

    def test_changed_source_copy_set_rejected(self):
        path = self.context("police_present")
        value = json.loads(path.read_text())
        del value["source_records"]["operator_activity"]
        path.write_text(json.dumps(value) + "\n")
        with self.assertRaisesRegex(ValueError, "copy set differs"):
            reviewed_context(path, PREFIX + "police_present")


if __name__ == "__main__":
    unittest.main()
