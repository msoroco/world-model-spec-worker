import sys
import tempfile
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE.parents[1] / "runtime" / "scenario_pipeline"))
from finalizer import finalize, measurement
from test_entry_measurements import write_sources


class FinalizerTests(unittest.TestCase):
    def test_entry_measurement_preserves_legal_uncertainty(self):
        report = {"first_body_entry": {"ego": {"frame": 11}, "other": {"frame": 12}},
                  "ego_minus_other_entry_time_s": -.05,
                  "other_is_to_ego_right": True,
                  "geometric_yield_candidate": "ego",
                  "sources": {"crossing_history.jsonl": "hash"}}
        record = measurement(report)
        self.assertIn("unresolved", record["right_of_way_judgment"])
        self.assertEqual(record["source_hashes"], report["sources"])
        self.assertNotIn("matched", record)

    def test_finalizer_rejects_missing_saved_sources(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            with self.assertRaisesRegex(ValueError, "Missing required source: config.json"):
                finalize(root, root / "analysis.json")

    def test_saved_source_finalization_writes_source_bound_result(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            write_sources(root)
            import json
            geometry = json.loads((root / "road_geometry.json").read_text())
            geometry["device_review"] = {"official_device_controls_crossing": False}
            (root / "road_geometry.json").write_text(json.dumps(geometry))
            (root / "config.json").write_text(json.dumps({
                "selected_case_id": "testing__C125714__NRS-484B-250-2__motor_vehicle_driver__synthetic_test",
                "law_id": "NRS-484B-250-2", "cell_id": "C125714",
                "duration_s": .15, "rate_hz": 20,
                "recording_description": {"purpose": "CPU synthetic source test"},
                "physical_completion": {"context_sources": ["road_geometry.json"]}}))
            (root / "trace.jsonl").write_text("".join(json.dumps({
                "frame": 10+i, "time_s": .5+i*.05, "position_m": [i,0,0]})+"\n"
                for i in range(3)))
            (root / "controller_history.jsonl").write_text("".join(json.dumps({
                "frame": 10+i, "time_s": .5+i*.05,
                "other_inside_before_tick": False,
                "other_entered_once": False,
                "ego_control": {"hold": True}})+"\n" for i in range(3)))
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text("{}\n")
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (name + ".mkv")).write_bytes(b"placeholder; no media acceptance claimed")
            payload = finalize(root, root / "analysis.json")
            result = json.loads((root / "result.json").read_text())
            self.assertEqual(result["provenance_kind"], "synthetic_fixture")
            self.assertFalse(result["physical_acceptance_claimed"])
            self.assertIn("unresolved", payload["right_of_way_judgment"])
            self.assertTrue((root / "channels/entry_context.json").is_file())
            self.assertTrue((root / "channels/yield_control.json").is_file())
            self.assertIn("yield_control_attempt", json.loads((root / "analysis.json").read_text())["measurements"])


if __name__ == "__main__":
    unittest.main()
