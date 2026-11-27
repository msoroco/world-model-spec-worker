import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("transit_analysis", ROOT / "analysis.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class SavedTransitTests(unittest.TestCase):
    def setUp(self):
        scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"])
        scratch.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def materialize(self, phase):
        fixture = json.loads((ROOT / ("diagnostic-" + phase + ".json")).read_text())
        for name in (*analysis.REQUIRED, "acquisition.json"):
            path = self.root / name
            path.write_text(fixture["files"][name])

    def test_waiting_and_boarding_original_motion(self):
        self.materialize("waiting_at_stop")
        waiting, _, _, _ = analysis.measure(self.root)
        self.assertEqual(waiting["door_approach_m"], 0)
        self.assertEqual(waiting["passenger_phase"], "waiting_at_stop")
        self.assertEqual(waiting["legal_proper_caution_verdict"], "unresolved")
        self.materialize("boarding_bus")
        boarding, _, _, _ = analysis.measure(self.root)
        self.assertGreater(boarding["door_approach_m"], 0)
        self.assertFalse(boarding["actual_bus_door_verified"])

    def test_missing_or_tampered_original_source_rejected(self):
        self.materialize("boarding_bus")
        (self.root / "encounter-history.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source"):
            analysis.measure(self.root)
        self.materialize("boarding_bus")
        with (self.root / "encounter-history.jsonl").open("a") as stream:
            stream.write("{}\n")
        with self.assertRaisesRegex(ValueError, "stale original Native source"):
            analysis.measure(self.root)

    def test_frame_and_reported_geometry_rechecked(self):
        self.materialize("boarding_bus")
        path = self.root / "encounter-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[2]["pedestrian_bus_door_region_gap_m"] = 99
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        import hashlib
        acquisition = json.loads((self.root / "acquisition.json").read_text())
        acquisition["encounter-history.jsonl"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.root / "acquisition.json").write_text(json.dumps(acquisition))
        with self.assertRaisesRegex(ValueError, "differs from original bodies"):
            analysis.measure(self.root)


if __name__ == "__main__":
    unittest.main()
