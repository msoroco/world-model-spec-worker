import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from original_motion_consistency import check
from test_delivery_audit import DeliveryAuditTest


class MotionConsistencyTest(unittest.TestCase):
    def setUp(self):
        fixture = DeliveryAuditTest("test_complete_source_chain_joins_all_frames")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        self.motion = fixture.motion
        self.write_independent_sources()

    def write_independent_sources(self):
        trace = []
        commands = []
        for row in self.motion:
            trace.append({"frame": row["frame"], "time_s": row["time_s"],
                          "position_m": row["position_m"],
                          "heading_deg": row["yaw_deg"], "speed_mps": 4.0,
                          "control": {"throttle": 0.2, "brake": 0.0, "steer": 0.0}})
            commands.append({"frame": row["frame"], "time_s": row["time_s"],
                             "control": {"throttle": 0.2, "brake": 0.0,
                                         "steer": 0.0, "finished": False}})
        (self.root / "trace.jsonl").write_text("".join(json.dumps(row) + "\n" for row in trace))
        (self.root / "taxi-controller-history.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in commands))
        self.fixture.seal()

    def audit(self):
        return check(self.root, "near_stand", self.fixture.map, self.fixture.layout)

    def change(self, name, index, field, value):
        path = self.root / name
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[index][field] = value
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture.seal()

    def test_original_pose_and_controls_join(self):
        result = self.audit()
        self.assertTrue(result["passed"])
        self.assertEqual(result["frames"], len(self.motion))
        self.assertFalse(result["physical_or_legal_acceptance"])

    def test_pipeline_pose_drift_rejected_even_with_updated_seal(self):
        path = self.root / "trace.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[8]["position_m"][0] += 0.2
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture.seal()
        with self.assertRaisesRegex(ValueError, "independent Native pose differs"):
            self.audit()

    def test_pipeline_heading_drift_rejected(self):
        self.change("trace.jsonl", 8, "heading_deg", self.motion[8]["yaw_deg"] + 20)
        with self.assertRaisesRegex(ValueError, "independent Native heading differs"):
            self.audit()

    def test_issued_applied_control_mismatch_rejected(self):
        path = self.root / "taxi-controller-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[8]["control"]["throttle"] = 0.4
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture.seal()
        with self.assertRaisesRegex(ValueError, "issued and applied control differ"):
            self.audit()

    def test_out_of_range_control_rejected(self):
        path = self.root / "taxi-controller-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[8]["control"]["steer"] = 2.0
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture.seal()
        with self.assertRaisesRegex(ValueError, "control outside Native range"):
            self.audit()

    def test_missing_completion_flag_rejected(self):
        path = self.root / "taxi-controller-history.jsonl"
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        del rows[8]["control"]["finished"]
        path.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.fixture.seal()
        with self.assertRaisesRegex(ValueError, "controller completion flag absent"):
            self.audit()


if __name__ == "__main__":
    unittest.main()
