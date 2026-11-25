import importlib.util
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from test_saved_entry import make_attempt, CASE


SOURCE = Path(__file__).resolve().parents[1] / "comparison_audit.py"
SPEC = importlib.util.spec_from_file_location("c227824_comparison_audit", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def report(case, device="none", request="entry", entered=True):
    devices = [] if device == "none" else [{"official": True, "indication": device}]
    event = {"frame": 2, "facing_traffic_signal": {"official": True, "indication": "steady_red_alone"},
             "other_devices": devices} if entered else None
    return {"case_id": case, "map_sha256": "map", "highway_boundary_sha256": "boundary",
            "facing_signal_id": "red-1", "actor_blueprint": "walker.pedestrian.test",
            "route_id": "crossing-1", "camera_plan_sha256": "cameras",
            "entry_request": request, "planned_device_indication": device,
            "measurement": {"first_entry": event, "entry_observed": entered,
                            "measurement_only": True, "legal_permission_determined": False}}


class ComparisonAuditTests(unittest.TestCase):
    def test_exact_saved_attempt_pair_and_changed_source_rejection(self):
        safe = Path(__file__).resolve().parents[3] / ".runtime-work"
        safe.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=safe) as temporary:
            root = Path(temporary)
            left, right = root / "left", root / "right"
            left.mkdir()
            right.mkdir()
            make_attempt(left)
            make_attempt(right)
            wait_case = CASE.rsplit("__", 1)[0] + "__red_no_device_wait"
            for name in ("scene.json", "walker-body-history.jsonl", "signal-history.jsonl",
                         "device-history.jsonl", "camera-frame-joins.jsonl"):
                path = right / name
                path.write_text(path.read_text().replace(CASE, wait_case))
            scene = json.loads((right / "scene.json").read_text())
            scene["entry_request"] = "wait"
            (right / "scene.json").write_text(json.dumps(scene) + "\n")
            body = right / "walker-body-history.jsonl"
            rows = [json.loads(line) for line in body.read_text().splitlines()]
            for row in rows:
                row["body_polygon_xy_m"] = [[-2, 3], [-1, 3], [-1, 4], [-2, 4]]
            body.write_text("".join(json.dumps(row) + "\n" for row in rows))
            manifest = json.loads((right / "acquisition.json").read_text())
            for name in ("scene.json", "walker-body-history.jsonl", "signal-history.jsonl",
                         "device-history.jsonl", "camera-frame-joins.jsonl"):
                manifest[name]["sha256"] = hashlib.sha256((right / name).read_bytes()).hexdigest()
            (right / "acquisition.json").write_text(json.dumps(manifest) + "\n")
            result = MODULE.audit_attempts(left, right, "red_entry_vs_wait",
                                           SOURCE.parent / "case-plan.json")
            self.assertTrue(result["diagnostic_fixture"])
            self.assertTrue(result["diagnostic_audit_passed"])
            self.assertFalse(result["physical_acceptance_claimed"])
            output = root / "comparison-audit.json"
            self.assertEqual(MODULE.main(["--left-attempt", str(left),
                                          "--right-attempt", str(right),
                                          "--comparison-id", "red_entry_vs_wait",
                                          "--output", str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())["case_ids"],
                             [CASE, wait_case])
            with self.assertRaisesRegex(ValueError, "exact comparison pair"):
                MODULE.audit_attempts(right, left, "red_entry_vs_wait",
                                      SOURCE.parent / "case-plan.json")
            body.write_text(body.read_text() + "{}\n")
            with self.assertRaisesRegex(ValueError, "saved source hash mismatch"):
                MODULE.audit_attempts(left, right, "red_entry_vs_wait",
                                      SOURCE.parent / "case-plan.json")

    def test_accepts_bound_entry_wait_pair(self):
        result = MODULE.audit_pair(report("a"), report("b", request="wait", entered=False),
                                   comparison_id="entry_vs_wait", deliberate_difference="entry_request")
        self.assertTrue(result["diagnostic_audit_passed"])
        self.assertFalse(result["physical_acceptance_claimed"])

    def test_accepts_separate_walk_device_pair(self):
        result = MODULE.audit_pair(report("a"), report("b", device="walk"),
                                   comparison_id="walk", deliberate_difference="other_device_indication")
        self.assertEqual(result["case_ids"], ["a", "b"])

    def test_rejects_changed_fixed_boundary_and_missing_device(self):
        changed = report("b", device="walk")
        changed["highway_boundary_sha256"] = "other"
        with self.assertRaisesRegex(ValueError, "fixed comparison condition"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")
        changed = report("b", device="walk")
        changed["measurement"]["first_entry"]["other_devices"] = []
        with self.assertRaisesRegex(ValueError, "planned device disagrees"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")

    def test_rejects_missing_entry_source_and_red_state(self):
        changed = report("b", device="walk", entered=False)
        with self.assertRaisesRegex(ValueError, "lacks observed first entry"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")
        changed = report("b", device="walk")
        changed["measurement"]["first_entry"]["facing_traffic_signal"]["indication"] = "other"
        with self.assertRaisesRegex(ValueError, "steady red"):
            MODULE.audit_pair(report("a"), changed, comparison_id="walk",
                              deliberate_difference="other_device_indication")


if __name__ == "__main__":
    unittest.main()
