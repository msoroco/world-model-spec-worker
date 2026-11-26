"""Synthetic 900-frame protocol test; no physical or legal acceptance claim."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from saved_finalizer import finalize
from school_scene_construction import ASSIGNMENT, SOURCES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FinalizerTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.case_id = ASSIGNMENT + "__beacon_flashing_15_1"
        self.context_path = self.root / "context.json"
        self.trace_path = self.root / "original-trace.jsonl"
        self.receipt_path = self.root / "receipt.json"
        context = {"case_id": self.case_id, "map_sha256": "a" * 64,
                   "local_datetime": "2026-11-26T12:00:00-08:00",
                   "operation_end_local": "2026-11-26T16:00:00-08:00",
                   "next_operation_start_local": "2026-11-27T08:00:00-08:00",
                   "class_start_local": "2026-11-26T08:00:00-08:00",
                   "class_end_local": "2026-11-26T16:00:00-08:00",
                   "school_in_session_today": True,
                   "operational_beacon_designation": True}
        for name in SOURCES:
            context[name + "_source"] = "synthetic protocol source " + name
        self.context_path.write_text(json.dumps(context) + "\n")
        self.write_rows(900)

    def write_rows(self, count):
        with self.trace_path.open("w") as stream:
            for index in range(count):
                stream.write(json.dumps({"frame": index, "time_s": index / 20,
                                         "bus_speed_mps": 15.1 / 2.2369362921,
                                         "inside_designated_zone": True,
                                         "beacon_yellow_lights_lit": [index % 2 == 0, index % 2 != 0],
                                         "sign_limit_active": True,
                                         "children_actor_ids": ["child_1"]}) + "\n")
        self.receipt_path.write_text(json.dumps({
            "assignment_id": ASSIGNMENT, "case_id": self.case_id,
            "source_kind": "original_native_capture", "diagnostic_fixture": False,
            "context_sha256": sha(self.context_path),
            "trace_sha256": sha(self.trace_path), "fps": 20,
            "frame_count": count}) + "\n")

    def test_recomputed_stable_bus_speed_and_truthful_limits(self):
        result = finalize(self.case_id, self.context_path, self.trace_path, self.receipt_path)
        self.assertAlmostEqual(result["steady_state_bus_speed_mph_median"], 15.1)
        self.assertEqual(result["steady_state_selected_zone_sample_count"], 600)
        self.assertTrue(result["engineering_target_within_0_25_mph"])
        self.assertEqual(result["physical_acceptance"], "unverified")
        self.assertEqual(result["legal_speed_rule_judgment"], "unresolved")

    def test_short_original_trace_rejected(self):
        self.write_rows(899)
        with self.assertRaisesRegex(ValueError, "900-frame"):
            finalize(self.case_id, self.context_path, self.trace_path, self.receipt_path)


if __name__ == "__main__":
    unittest.main()
