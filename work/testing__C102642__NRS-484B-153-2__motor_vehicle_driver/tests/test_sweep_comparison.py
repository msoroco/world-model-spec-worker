import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sweep_comparison_audit import audit


class SweepComparisonTests(unittest.TestCase):
    def paths(self):
        return [ROOT / "cases" / f"door_interference_physical_range-{i:04d}" /
                "diagnostic-sources" for i in range(3)]

    def test_diagnostic_positive_and_original_mode_rejection(self):
        result = audit(self.paths(), allow_diagnostic=True)
        self.assertEqual(len(result["cases"]), 3)
        self.assertEqual([row["requested_engineering_m"] for row in result["cases"]],
                         [.25, 1.25, .75])
        self.assertIsNone(result["legal_interference"])
        with self.assertRaisesRegex(ValueError, "original Native clearance frames"):
            audit(self.paths())

    def test_fixed_source_and_original_measurement_tamper(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as directory:
            clone = Path(directory) / "middle"
            shutil.copytree(self.paths()[1], clone)
            paths = self.paths()
            paths[1] = clone
            trace_path = clone / "native-trace.json"
            intent_path = clone / "door-source.json"
            trace = json.loads(trace_path.read_text())
            trace["fixed_context"]["map_sha256"] = "0" * 64
            trace_path.write_text(json.dumps(trace) + "\n")
            intent = json.loads(intent_path.read_text())
            intent["source_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
            intent_path.write_text(json.dumps(intent) + "\n")
            with self.assertRaisesRegex(ValueError, "changed fixed site or route"):
                audit(paths, allow_diagnostic=True)
            trace["fixed_context"]["map_sha256"] = json.loads(
                (self.paths()[1] / "native-trace.json").read_text())["fixed_context"]["map_sha256"]
            trace["frames"][1].pop("act_envelope_xy")
            trace_path.write_text(json.dumps(trace) + "\n")
            intent["source_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
            intent_path.write_text(json.dumps(intent) + "\n")
            with self.assertRaises((KeyError, ValueError)):
                audit(paths, allow_diagnostic=True)

    def test_passing_speed_drift_and_missing_trace_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parents[1] / ".runtime-work") as directory:
            clone = Path(directory) / "middle"
            shutil.copytree(self.paths()[1], clone)
            paths = self.paths()
            paths[1] = clone
            trace_path = clone / "native-trace.json"
            intent_path = clone / "door-source.json"
            trace = json.loads(trace_path.read_text())
            trace["frames"][1]["passing_speed_mps"] += 1.0
            trace_path.write_text(json.dumps(trace) + "\n")
            intent = json.loads(intent_path.read_text())
            intent["source_trace_sha256"] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
            intent_path.write_text(json.dumps(intent) + "\n")
            with self.assertRaisesRegex(ValueError, "passing speed history changed"):
                audit(paths, allow_diagnostic=True)
            trace_path.unlink()
            with self.assertRaises(FileNotFoundError):
                audit(paths, allow_diagnostic=True)


if __name__ == "__main__":
    unittest.main()
