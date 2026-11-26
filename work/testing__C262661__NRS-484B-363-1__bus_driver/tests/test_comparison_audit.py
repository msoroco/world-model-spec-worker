"""Diagnostic packets exercise independent comparison rejection paths."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from comparison_audit import CHANGES, audit
from school_scene_construction import ASSIGNMENT, SOURCES


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        scratch = Path.cwd() / ".runtime-work"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def packet(self, name, speed):
        case_id = ASSIGNMENT + "__" + name
        folder = self.root / name
        folder.mkdir(exist_ok=True)
        context = {"case_id": case_id, "map_sha256": "a" * 64,
                   "zone_polygon_xy_m": [[0, 0], [100, 0], [100, 20], [0, 20]],
                   "route_xy_m": [[-20, 10], [120, 10]],
                   "local_datetime": "2026-11-26T12:00:00-08:00",
                   "operation_end_local": "2026-11-26T16:00:00-08:00",
                   "next_operation_start_local": "2026-11-27T08:00:00-08:00",
                   "class_start_local": "2026-11-26T08:00:00-08:00",
                   "class_end_local": "2026-11-26T16:00:00-08:00",
                   "school_in_session_today": True,
                   "operational_beacon_designation": True,
                   "vehicle_blueprint": "vehicle.school_bus"}
        for source in SOURCES:
            context[source + "_source"] = "diagnostic protocol packet: " + source
            context[source + "_source_sha256"] = "f" * 64
        trace = [{"frame": index, "time_s": index / 20,
                  "bus_speed_mps": speed / 2.2369362921,
                  "inside_designated_zone": True,
                  "beacon_yellow_lights_lit": [index == 0, index == 1],
                  "sign_limit_active": True,
                  "children_actor_ids": ["child_1"]} for index in range(2)]
        context_path = folder / "context.json"
        trace_path = folder / "original-trace.jsonl"
        context_path.write_text(json.dumps(context) + "\n")
        trace_path.write_text("".join(json.dumps(row) + "\n" for row in trace))
        receipt = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                   "source_kind": "original_native_capture", "diagnostic_fixture": False,
                   "context_sha256": sha(context_path), "trace_sha256": sha(trace_path),
                   "fps": 20, "frame_count": 2}
        (folder / "receipt.json").write_text(json.dumps(receipt) + "\n")
        return folder

    def test_speed_comparison_and_failed_motion(self):
        left = self.packet("beacon_flashing_14_9", 14.9)
        right = self.packet("beacon_flashing_15_0", 15.0)
        result = audit("below_versus_at_15_mph", left, right)
        self.assertEqual(result["observed_difference"], "speed")
        self.assertEqual(result["physical_acceptance"], "unverified")
        bad = json.loads((right / "original-trace.jsonl").read_text().splitlines()[0])
        rows = [bad, dict(bad, frame=1, time_s=.05)]
        for row in rows:
            row["bus_speed_mps"] = 14.9 / 2.2369362921
        (right / "original-trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows))
        receipt = json.loads((right / "receipt.json").read_text())
        receipt["trace_sha256"] = sha(right / "original-trace.jsonl")
        (right / "receipt.json").write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "speed comparison order"):
            audit("below_versus_at_15_mph", left, right)

    def test_fixed_source_change_rejected(self):
        left = self.packet("beacon_flashing_14_9", 14.9)
        right = self.packet("beacon_flashing_15_0", 15.0)
        context = json.loads((right / "context.json").read_text())
        context["bus_route_source_sha256"] = "e" * 64
        (right / "context.json").write_text(json.dumps(context) + "\n")
        receipt = json.loads((right / "receipt.json").read_text())
        receipt["context_sha256"] = sha(right / "context.json")
        (right / "receipt.json").write_text(json.dumps(receipt) + "\n")
        with self.assertRaisesRegex(ValueError, "fixed school source changed"):
            audit("below_versus_at_15_mph", left, right)

    def test_all_twelve_declared_contrasts(self):
        plan = json.loads((ROOT / "case-plan.json").read_text())
        cases = {case["case_id"]: case for case in plan["cases"]}
        self.assertEqual(len(plan["comparisons"]), 12)
        for comparison in plan["comparisons"]:
            comparison_id = comparison["comparison_id"]
            variable, changed_sources = CHANGES[comparison_id]
            left_case, right_case = (cases[case_id] for case_id in comparison["case_ids"])
            left = self.packet(left_case["case_id"].split("__")[-1], left_case["speed_target_mph"])
            right = self.packet(right_case["case_id"].split("__")[-1], right_case["speed_target_mph"])
            context_path = right / "context.json"
            trace_path = right / "original-trace.jsonl"
            receipt_path = right / "receipt.json"
            context = json.loads(context_path.read_text())
            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]
            if changed_sources:
                context[changed_sources[0] + "_source_sha256"] = "e" * 64
            if variable == "session":
                context["school_in_session_today"] = False
            elif variable == "clock":
                context["local_datetime"] = (
                    "2026-11-26T16:31:00-08:00" if comparison_id == "half_hour_after_operation"
                    else "2026-11-27T07:29:00-08:00")
            elif variable == "lamps":
                for row in rows:
                    row["beacon_yellow_lights_lit"] = [False, False]
            elif variable == "sign":
                for row in rows:
                    row["sign_limit_active"] = False
            elif variable == "lamp_count":
                for row in rows:
                    row["beacon_yellow_lights_lit"] = [True]
            elif variable == "alternation":
                for row in rows:
                    row["beacon_yellow_lights_lit"] = [True, False]
            elif variable == "zone":
                for row in rows:
                    row["inside_designated_zone"] = False
            elif variable == "children":
                for row in rows:
                    row["children_actor_ids"] = []
            elif variable == "vehicle":
                context["vehicle_blueprint"] = "vehicle.car"
            context_path.write_text(json.dumps(context) + "\n")
            trace_path.write_text("".join(json.dumps(row) + "\n" for row in rows))
            receipt = json.loads(receipt_path.read_text())
            receipt["context_sha256"] = sha(context_path)
            receipt["trace_sha256"] = sha(trace_path)
            receipt_path.write_text(json.dumps(receipt) + "\n")
            with self.subTest(comparison=comparison_id):
                result = audit(comparison_id, left, right)
                self.assertEqual(result["observed_difference"], variable)


if __name__ == "__main__":
    unittest.main()
