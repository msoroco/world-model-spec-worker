import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
CASE = ROOT.name + "__source_verified_below_80"


class FinalizerTests(unittest.TestCase):
    def fixture(self, attempt):
        (attempt / "capture").mkdir()
        context = {"native_map_id": "TownX", "subject_actor_id": 12,
                   "subject_blueprint_id": "vehicle.sample", "route_source": "native-route",
                   "alley_source": "map-front-camera", "access_aisle_source": "map-side-camera"}
        (attempt / "road_context.json").write_text(json.dumps(context))
        config = {"selected_case_id": CASE, "requested_speed_mph": 79.99,
                  "recording_description": {"channels": [{"name": "kin.speed"}]}}
        (attempt / "config.json").write_text(json.dumps(config))
        motion = [{"frame": 100 + i, "time_s": 1 + i * .05,
                   "subject_actor_id": 12, "speed_source": "actor.get_velocity",
                   "velocity_mps": [mph * .44704, 0, 0]}
                  for i, mph in enumerate((60, 79.99))]
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(motion)]
        (attempt / "subject_motion.jsonl").write_text("".join(json.dumps(row)+"\n" for row in motion))
        (attempt / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
        (attempt / "trace.jsonl").write_text("".join(json.dumps(row)+"\n" for row in motion))
        (attempt / "capture/evidence.jsonl").write_text('{"frame":100}\n')
        for name in ("overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"):
            (attempt / name).write_bytes(b"textual test placeholder")

    def command(self, attempt):
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO / "runtime/scenario_pipeline")
        return subprocess.run([sys.executable, str(ROOT / "finalizer.py"),
                               "--attempt", str(attempt), "--output", str(attempt / "analysis-report.json")],
                              env=env, capture_output=True, text=True)

    def test_saved_only_result_and_source_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            self.fixture(attempt)
            before = hashlib.sha256((attempt / "subject_motion.jsonl").read_bytes()).hexdigest()
            run = self.command(attempt)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(before, hashlib.sha256((attempt / "subject_motion.jsonl").read_bytes()).hexdigest())
            result = json.loads((attempt / "result.json").read_text())
            report = json.loads((attempt / "analysis-report.json").read_text())
            self.assertEqual(result["case_id"], CASE)
            self.assertAlmostEqual(result["measured_values"]["sampled_peak_speed_mph"], 79.99)
            self.assertEqual(report["measurements"]["sampled_peak_speed_mph"]["sources"]["subject_motion.jsonl"], before)
            self.assertNotIn("legal_verdict", result)
            sys.path.insert(0, str(REPO / "runtime/scenario_pipeline"))
            from worker_exchange.measurement_contract import validate, verify_report
            contract = json.loads((ROOT / "measurement-contract.json").read_text())
            plan = json.loads((ROOT / "case-plan.json").read_text())
            validate(contract, plan["requirement_dispositions"], (ROOT / "finalizer.py").read_text(), CASE)
            verify_report(contract, report, attempt)

    def test_missing_case_source_rejected_without_result(self):
        with tempfile.TemporaryDirectory() as temp:
            attempt = Path(temp)
            self.fixture(attempt)
            (attempt / "subject_motion.jsonl").unlink()
            run = self.command(attempt)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("Missing required source: subject_motion.jsonl", run.stderr)
            self.assertFalse((attempt / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
