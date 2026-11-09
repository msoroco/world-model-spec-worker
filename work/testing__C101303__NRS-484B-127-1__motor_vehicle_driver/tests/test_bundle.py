import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


class BundleTests(unittest.TestCase):
    def test_lazy_config(self):
        runner = module("runner")
        config = json.loads((ROOT / "config.json").read_text())
        self.assertEqual(runner.check(config)["rate_hz"], 20)
        self.assertEqual(len(config["cameras"]), 4)

    def test_saved_measurement_and_frame_rejection(self):
        finalizer = module("finalize")
        body = lambda x: [[x - 1, -1, 0], [x + 1, -1, 0],
                          [x + 1, 1, 0], [x - 1, 1, 0]]
        samples = [{"frame": i + 10, "time_s": i * .05,
                    "ego_body_vertices_m": body(i), "lead_body_vertices_m": body(i + 20),
                    "ego_lane_id": -1, "lead_lane_id": -1,
                    "ego_speed_mps": 8.0, "lead_speed_mps": 8.0,
                    "lane_change_requested": False, "weather": {"wetness": 0.0}}
                   for i in range(3)]
        mapping = [{"video_frame": i, "carla_frame": i + 10, "time_s": i * .05}
                   for i in range(3)]
        value = finalizer.following_measurement(samples, mapping, {"crest_elevation_m": 5})
        self.assertEqual(value["separation_m"]["first"], 20)
        self.assertEqual(value["pre_change_samples"], 3)
        mapping[1]["carla_frame"] = 99
        with self.assertRaisesRegex(ValueError, "frame/time join"):
            finalizer.following_measurement(samples, mapping, {"crest_elevation_m": 5})

    def test_missing_case_specific_source(self):
        finalizer = module("finalize")
        with tempfile.TemporaryDirectory() as temp:
            (pathlib.Path(temp) / "config.json").write_text((ROOT / "config.json").read_text())
            with self.assertRaisesRegex(ValueError, "Missing required source: following_samples.jsonl"):
                finalizer.analyze(temp, pathlib.Path(temp) / "report.json")

    def test_physical_lane_transition_three_outcomes(self):
        finalizer = module("finalize")
        complete = [{"frame": i, "ego_lane_id": -1 if i < 20 else -2,
                     "lane_change_requested": i >= 20} for i in range(45)]
        self.assertEqual(finalizer.lane_transition_status(complete, -2)["status"], "met")
        incomplete = [dict(row) for row in complete]
        incomplete[-1]["ego_lane_id"] = -1
        self.assertEqual(finalizer.lane_transition_status(incomplete, -2)["status"], "not_met")
        self.assertEqual(finalizer.lane_transition_status([], -2)["status"], "unverified")

    def test_finalizer_writes_native_recording_views(self):
        finalizer = module("finalize")
        runtime = next((p / "runtime/scenario_pipeline" for p in ROOT.parents
                        if (p / "runtime/scenario_pipeline").is_dir()), None)
        self.assertIsNotNone(runtime)
        sys.path.insert(0, str(runtime))
        from batch_pipeline.validation import recording_evidence
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "config.json").write_text((ROOT / "config.json").read_text())
            (root / "surface_context.json").write_text(json.dumps({
                "target_lane_id": -2, "crest_elevation_m": 5}))
            (root / "acquisition-provenance.json").write_text(json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}))
            body = lambda x: [[x - 1, -1, 0], [x + 1, -1, 0],
                              [x + 1, 1, 0], [x - 1, 1, 0]]
            with (root / "following_samples.jsonl").open("w") as samples, \
                 (root / "video_frames.jsonl").open("w") as frames, \
                 (root / "trace.jsonl").open("w") as trace:
                for i in range(20):
                    samples.write(json.dumps({"frame": i + 10, "time_s": i * .05,
                        "ego_body_vertices_m": body(i), "lead_body_vertices_m": body(i + 16),
                        "ego_lane_id": -1, "lead_lane_id": -1,
                        "ego_speed_mps": 8.0, "lead_speed_mps": 8.0,
                        "lane_change_requested": False, "weather": {"wetness": 0.0}}) + "\n")
                    frames.write(json.dumps({"video_frame": i, "carla_frame": i + 10,
                                             "time_s": i * .05}) + "\n")
                    trace.write(json.dumps({"frame": i + 10, "time_s": i * .05}) + "\n")
            for name in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (name + ".mkv")).write_text("fixture, not decoded footage")
            finalizer.analyze(root, root / "analysis-report.json")
            result = json.loads((root / "result.json").read_text())
            self.assertFalse(result["setup_confirmed"])
            self.assertFalse(result["maneuver_completed"])
            self.assertEqual(result["provenance_kind"], "synthetic_fixture")
            description = json.loads((root / "config.json").read_text())["recording_description"]
            sweep = [{"observable": "following.separation", "unit": "m",
                      "measurement": {"method": "first pre-change original body-center separation",
                                      "time_window": "pre-change original frame interval",
                                      "statistic": "first"}}]
            recording_evidence(result, description, lambda ref: root / ref,
                               sweep)


if __name__ == "__main__":
    unittest.main()
