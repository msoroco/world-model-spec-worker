import importlib.util
import json
import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


measure = load("crossing_measurements")
signs = load("yield_sign_control")


def body(x):
    return [[x, 1], [x, -1], [x - 2, 1], [x - 2, -1]]


class FakeSign:
    def __init__(self, valid):
        self.id, self.calls = 10, []
        def contains(point, transform):
            self.calls.append((point, transform))
            return valid
        self.trigger_volume = NS(contains=contains)

    def get_transform(self):
        return "native-sign-transform"


class FakeActors(list):
    def filter(self, pattern):
        assert pattern == "traffic.yield*"
        return self


class CrossingTests(unittest.TestCase):
    def fixture(self, root):
        context = {"native_map_id": "TownX", "intersection_id": 9,
                   "ego_highway_id": "highway-a", "other_highway_id": "highway-b",
                   "ego_road_id": 3, "other_road_id": 4,
                   "native_yield_sign_id": 10, "sign_governance_source": "native-trigger",
                   "yield_sign_video_source": "front-original", "intersection_polygon_source": "native-map-junction",
                   "yield_sign_erected": True, "yield_sign_governed_road_id": 3,
                   "physical_acceptance_claimed": False,
                   "intersection_polygon_xy_m": [[0, -5], [10, -5], [10, 5], [0, 5]]}
        (root / "junction_context.json").write_text(json.dumps(context))
        ego_x, other_x = [-20, -18, -10, 1], [-4, 1, 3, 5]
        rows = []
        for i in range(4):
            rows.append({"frame": 100+i, "time_s": 1+i*.05,
                         "native_yield_sign_id": 10,
                         "ego": {"intersection_id": 9, "road_id": 3,
                                 "distance_to_intersection_m": max(0, -ego_x[i]),
                                 "speed_mps": 3 if i != 2 else 0,
                                 "body_vertices_xy_m": body(ego_x[i])},
                         "other": {"intersection_id": 9, "road_id": 4,
                                   "distance_to_intersection_m": max(0, -other_x[i]),
                                   "speed_mps": 3, "body_vertices_xy_m": body(other_x[i])}})
        frames = [{"video_frame": i, "carla_frame": row["frame"], "time_s": row["time_s"]}
                  for i, row in enumerate(rows)]
        (root / "crossing_history.jsonl").write_text("".join(json.dumps(row)+"\n" for row in rows))
        (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))

    def test_native_yield_trigger_selection(self):
        wrong, right = FakeSign(False), FakeSign(True)
        world = NS(get_actors=lambda: FakeActors([wrong, right]))
        waypoint = NS(transform=NS(location="ego-approach-point"))
        self.assertIs(signs.find_governing_yield_sign(world, waypoint), right)
        self.assertEqual(right.calls, [("ego-approach-point", "native-sign-transform")])
        with self.assertRaisesRegex(ValueError, "found 0"):
            signs.find_governing_yield_sign(NS(get_actors=lambda: FakeActors([wrong])), waypoint)

    def test_other_first_at_yield_sign_and_context_rejections(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            report = measure.analyze(root)
            self.assertTrue(report["other_entered_before_ego_observed"])
            self.assertTrue(report["ego_approaching_at_other_entry_observed"])
            self.assertIn("unresolved", report["official_device_exclusion_judgment"])
            context = json.loads((root / "junction_context.json").read_text())
            context["yield_sign_governed_road_id"] = 4
            (root / "junction_context.json").write_text(json.dumps(context))
            with self.assertRaisesRegex(ValueError, "governing yield sign"):
                measure.analyze(root)

    def test_stale_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            frames[1]["carla_frame"] = 999
            (root / "video_frames.jsonl").write_text("".join(json.dumps(row)+"\n" for row in frames))
            with self.assertRaisesRegex(ValueError, "frame join"):
                measure.analyze(root)

    def test_900_frame_saved_finalizer_and_missing_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            # Retain the source-shaped context and replace the short diagnostic
            # with a complete 45-second, 20 Hz original-frame history.
            history, frames = [], []
            for i in range(900):
                # Bodies enter at 185 and 333 respectively; neither is inside
                # on the first frame. The other body eventually clears.
                other_x = -184 + i
                ego_x = -332 + i
                history.append({"frame": 1000 + i, "time_s": i / 20,
                    "native_yield_sign_id": 10,
                    "ego": {"intersection_id": 9, "road_id": 3,
                            "distance_to_intersection_m": max(0, -ego_x),
                            "speed_mps": 0 if 180 <= i <= 250 else 3,
                            "body_vertices_xy_m": body(ego_x)},
                    "other": {"intersection_id": 9, "road_id": 4,
                              "distance_to_intersection_m": max(0, -other_x),
                              "speed_mps": 3,
                              "body_vertices_xy_m": body(other_x)}})
                frames.append({"video_frame": i, "carla_frame": 1000 + i,
                               "time_s": i / 20})
            for name, values in (("crossing_history.jsonl", history),
                                 ("video_frames.jsonl", frames)):
                (root / name).write_text("".join(json.dumps(v) + "\n" for v in values))
            output = root / "diagnostic.json"
            report = measure.finalize(root, output)
            saved = json.loads(output.read_text())
            self.assertEqual(len(saved["samples"]), 900)
            self.assertEqual(saved["source_kind"], "original_frame_source_only")
            self.assertFalse(saved["physical_acceptance_claimed"])
            self.assertFalse(saved["legal_acceptance_claimed"])
            self.assertTrue(saved["other_entered_before_ego_observed"])
            self.assertTrue(saved["ego_approaching_at_other_entry_observed"])
            self.assertEqual(saved["sources"]["crossing_history.jsonl"],
                             hashlib.sha256((root / "crossing_history.jsonl").read_bytes()).hexdigest())
            self.assertEqual(report, saved)
            construction = json.loads((ROOT / "construction.json").read_text())
            config = next(json.loads(item["content"]) for item in construction["files"]
                          if item["path"] == "config.json")
            (root / "config.json").write_text(json.dumps(config))
            controls = [{"frame": row["frame"], "time_s": row["time_s"],
                         "other_conflict_clear": False,
                         "commands": {"ego": {"brake": 1 if 184 <= i <= 196 else 0}}}
                        for i, row in enumerate(history)]
            (root / "controller_history.jsonl").write_text("".join(
                json.dumps(row) + "\n" for row in controls))
            (root / "trace.jsonl").write_text("".join(
                json.dumps({"frame": row["frame"], "time_s": row["time_s"]}) + "\n"
                for row in history))
            (root / "capture").mkdir()
            (root / "capture/evidence.jsonl").write_text("\n")
            for camera in ("overview", "approach", "reference_corner", "driver_reference"):
                (root / (camera + ".mkv")).write_text("CPU fixture placeholder; no pixel claim\n")
            runtime_output = root / "runtime-analysis.json"
            measured = measure.runtime_finalize(root, runtime_output)
            from worker_exchange.measurement_contract import validate, verify_report
            contract = json.loads((ROOT / "measurement-contract.json").read_text())
            plan = json.loads((ROOT / "case-plan.json").read_text())
            self.assertEqual(len(validate(contract, plan["requirement_dispositions"],
                (ROOT / "crossing_measurements.py").read_text(), config["selected_case_id"])), 4)
            self.assertEqual(set(verify_report(contract,
                json.loads(runtime_output.read_text()), root)), set(measured))
            runtime_result = json.loads((root / "result.json").read_text())
            from batch_pipeline.validation import recording_evidence
            recording_evidence(runtime_result, config["recording_description"],
                               lambda reference: root / reference)
            missing_channel = dict(runtime_result)
            missing_channel["recording_evidence"] = [item for item in
                runtime_result["recording_evidence"] if item["name"] != "ego_speed"]
            with self.assertRaisesRegex(ValueError, "Missing recording evidence: ego_speed"):
                recording_evidence(missing_channel, config["recording_description"],
                                   lambda reference: root / reference)
            self.assertEqual(len(measured), 4)
            self.assertEqual(runtime_result["case_id"], config["selected_case_id"])
            self.assertTrue(runtime_result["measured_values"]["other_entered_before_ego_observed"])
            self.assertFalse(runtime_result["setup_confirmed"])
            self.assertFalse(json.loads(runtime_output.read_text())["physical_acceptance_claimed"])
            (root / "result.json").unlink()
            shutil.rmtree(root / "channels")
            (root / "video_frames.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "Missing required source: video_frames.jsonl"):
                measure.runtime_finalize(root, root / "negative-runtime-analysis.json")
            with self.assertRaisesRegex(ValueError, "Missing required source: video_frames.jsonl"):
                measure.finalize(root, output)

    def test_missing_original_frame_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.fixture(root)
            rows = [json.loads(line) for line in (root / "crossing_history.jsonl").read_text().splitlines()]
            frames = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
            rows[2]["frame"] = frames[2]["carla_frame"] = 103
            rows[3]["frame"] = frames[3]["carla_frame"] = 104
            for name, values in (("crossing_history.jsonl", rows),
                                 ("video_frames.jsonl", frames)):
                (root / name).write_text("".join(json.dumps(v) + "\n" for v in values))
            with self.assertRaisesRegex(ValueError, "Missing original frame"):
                measure.analyze(root)

    def test_yield_approach_controller(self):
        throttle, brake, phase = signs.step_ego(2, 4, True)
        self.assertEqual((throttle, phase), (0, "hold_for_other_body"))
        self.assertGreater(brake, 0)
        self.assertEqual(signs.step_ego(2, 0, False)[2], "clear_body_proceed")
        with self.assertRaisesRegex(ValueError, "occupancy"):
            signs.step_ego(2, 4, None)
        with self.assertRaisesRegex(ValueError, "Finite"):
            signs.step_ego(float("nan"), 4, True)


if __name__ == "__main__":
    unittest.main()
