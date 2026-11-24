"""Small synthetic source packets for the saved-speed comparison checker."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE = Path(__file__).with_name("audit_speed_comparison.py")
SPEC = importlib.util.spec_from_file_location("audit_speed_comparison", MODULE)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SavedSourceComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        context = {
            "sign_id": "synthetic-sign-30", "posted_mph": 30,
            "authority_source": "synthetic fixture only; public authority unverified",
            "highway_source": "synthetic fixture only; highway dedication unverified",
            "governed_direction": "eastbound", "zone_start_m": 10, "zone_end_m": 100,
        }
        context_hash = write(self.base / "context.json", context)
        cases = []
        for name, speed in (("below", 27), ("near_at", 29.75), ("above", 33)):
            rows = [{"frame": i, "time_s": i / 20, "x_m": 20 + i,
                     "speed_mps": speed / AUDIT.MPS_TO_MPH, "direction": "eastbound"}
                    for i in range(5)]
            path = self.base / (name + ".jsonl")
            path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
            cases.append({"case_id": name, "context_path": "context.json",
                          "context_sha256": context_hash, "trace_path": path.name,
                          "trace_sha256": AUDIT.digest(path)})
        self.spec = {"format": "posted-speed-source-comparison-v1",
                     "comparison_id": "synthetic-diagnostic", "cases": cases}
        write(self.base / "spec.json", self.spec)

    def test_three_distinct_saved_speeds_and_fixed_context(self):
        result = AUDIT.audit(self.base / "spec.json", min_frames=5, min_duration_s=0.2)
        self.assertTrue(result["passed"])
        self.assertEqual([round(c["max_measured_mph"], 2) for c in result["cases"]],
                         [27.0, 29.75, 33.0])
        self.assertEqual([c["governed_frames"] for c in result["cases"]], [5, 5, 5])

    def test_changed_sign_context_rejected(self):
        changed = dict(self.spec)
        changed["cases"] = [dict(c) for c in self.spec["cases"]]
        context = json.loads((self.base / "context.json").read_text())
        context["posted_mph"] = 35
        changed["cases"][2]["context_sha256"] = write(self.base / "changed.json", context)
        changed["cases"][2]["context_path"] = "changed.json"
        write(self.base / "changed-spec.json", changed)
        with self.assertRaisesRegex(ValueError, "comparison context changed"):
            AUDIT.audit(self.base / "changed-spec.json", min_frames=5, min_duration_s=0.2)

    def test_missing_trace_source_rejected(self):
        (self.base / "above.jsonl").unlink()
        with self.assertRaises(FileNotFoundError):
            AUDIT.audit(self.base / "spec.json", min_frames=5, min_duration_s=0.2)

    def test_incomplete_capture_rejected(self):
        with self.assertRaisesRegex(ValueError, "insufficient source frames"):
            AUDIT.audit(self.base / "spec.json", min_frames=600)

    def test_short_capture_rejected_even_with_enough_frames(self):
        with self.assertRaisesRegex(ValueError, "insufficient source duration"):
            AUDIT.audit(self.base / "spec.json", min_frames=5)


if __name__ == "__main__":
    unittest.main()
