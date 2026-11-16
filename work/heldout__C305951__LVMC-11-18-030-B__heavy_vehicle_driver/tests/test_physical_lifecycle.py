import unittest
import json
import ast
from copy import deepcopy
from math import atan2, hypot, pi
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import heavy_physical_outcome as physical
import heavy_lifecycle_fixture as lifecycle
import heavy_physical_fixture as fixture_runner
from heavy_lane_source import measure_footprint


class HeavyPhysicalLifecycleTest(unittest.TestCase):
    def test_saved_lateral_sweep_finalizer_and_audit(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        for branch in ("passing_boundary_crossing", "lawful_turn_preparation_boundary_crossing"):
            outputs = [fixture_runner.run(prefix + branch, "complete_motion",
                                          lateral_offset_m=offset)
                       for offset in (0.0, 1.1, 2.2)]
            clearances = [item["realized_observables"]["minimum_clearance_m"]
                          for item in outputs]
            with self.subTest(branch=branch):
                self.assertEqual([item["physical_checks"]["maneuver"]["status"]
                                  for item in outputs], ["not_met", "met", "met"])
                self.assertGreater(clearances[0], 0)
                self.assertLess(clearances[1], 0)
                self.assertGreater(clearances[0], clearances[1])
                self.assertGreater(clearances[1], clearances[2])
                self.assertTrue(all(item["diagnostic_fixture"] and
                                    not item["actual_native_capture"] and
                                    not item["physical_acceptance_claimed"]
                                    for item in outputs))

    def test_passing_and_turn_source_footprint_sweep(self):
        """Probe physical clearance from returned source geometry, with legal status unset."""
        here = Path(__file__).resolve().parents[1]
        root = here.parents[1]
        sys.path.insert(0, str(root / "runtime/scenario_pipeline"))
        from worker_exchange.fixture_recipe import materialize
        manifest = json.loads((here / "provisional-manifest.json").read_text())
        for branch in ("passing_boundary_crossing", "lawful_turn_preparation_boundary_crossing"):
            entry = next(e for e in manifest["cases"] if e["case_id"].endswith("__" + branch))
            with TemporaryDirectory(dir=root / ".runtime-work") as directory:
                fixture = Path(directory) / "fixture"
                materialize(root, root / entry["fixture_recipe"], fixture)
                source = json.loads((fixture / "heavy_lane_sources.jsonl").read_text().splitlines()[0])
                heading_x, heading_y = source["lane"]["heading_xy"]
                right_x, right_y = heading_y, -heading_x
                results = []
                for offset in (0.0, 1.1, 2.2):
                    row = deepcopy(source)
                    for component in row["heavy_vehicle_components"]:
                        for corner in component["corners_xy_m"]:
                            corner[0] += offset * right_x
                            corner[1] += offset * right_y
                    measurement = measure_footprint(row)
                    self.assertEqual(len(measurement["component_clearances"]),
                                     len(source["heavy_vehicle_components"]))
                    results.append(measurement["minimum_clearance_m"])
                with self.subTest(branch=branch):
                    self.assertAlmostEqual(results[0], 0.75, places=5)
                    self.assertAlmostEqual(results[1], -0.35, places=5)
                    self.assertAlmostEqual(results[2], -1.45, places=5)
                    self.assertGreater(results[0], results[1])
                    self.assertGreater(results[1], results[2])
                print("synthetic source footprint sweep", branch, results)

    def test_passing_and_turn_lateral_control_sweep(self):
        """The authored offset must change the actual steering command on both branches."""
        here = Path(__file__).resolve().parents[1]
        for branch in ("passing", "turn"):
            construction = json.loads((here / (branch + "-construction.json")).read_text())
            sources = {item["path"]: item["content"] for item in construction["files"]}
            config = json.loads(sources["config.json"])
            self.assertEqual(config["engineering"]["lateral_offset_m"], 2.2)
            tree = ast.parse(sources["runner.py"])
            function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                            and node.name == "control_step")
            scope = {"atan2": atan2, "hypot": hypot, "pi": pi}
            exec(compile(ast.Module(body=[function], type_ignores=[]), branch + "-runner.py", "exec"), scope)
            point = lambda x, y: SimpleNamespace(x=x, y=y)
            transform = SimpleNamespace(location=point(0.0, 0.0),
                                        get_forward_vector=lambda: point(1.0, 0.0))
            actor = SimpleNamespace(get_transform=lambda: transform,
                                    get_velocity=lambda: point(0.0, 0.0))
            target = SimpleNamespace(transform=SimpleNamespace(location=point(10.0, 0.0),
                                      get_right_vector=lambda: point(0.0, -1.0)))
            commands = [scope["control_step"](actor, target, 4.0, offset)
                        for offset in (0.0, 1.1, 2.2)]
            with self.subTest(branch=branch):
                self.assertEqual(commands[0]["steer"], 0.0)
                self.assertGreater(commands[0]["steer"], commands[1]["steer"])
                self.assertGreater(commands[1]["steer"], commands[2]["steer"])
                self.assertTrue(all(command["throttle"] == 0.6 for command in commands))

    def test_saved_review_rejects_synthetic_and_missing_native_provenance(self):
        case = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__within_marked_lane"
        fixture = {"case_id": case, "fixture_only": True,
                   "review_method": "frame_by_frame_originals",
                   "reviewer_id": "synthetic-cpu-fixture",
                   "reviewed_at_utc": "fixture-clock-only"}
        with self.assertRaisesRegex(ValueError, "Synthetic pixel review"):
            physical.audit_saved("unused", case, fixture)
        real_without_provenance = dict(fixture, fixture_only=False)
        with self.assertRaisesRegex(ValueError, "Native capture provenance"):
            physical.audit_saved("unused", case, real_without_provenance)

    def test_saved_review_rejects_incomplete_participant_history(self):
        case = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__within_marked_lane"
        review = {"case_id": case, "fixture_only": True,
                  "review_method": "frame_by_frame_originals",
                  "reviewer_id": "synthetic-cpu-fixture",
                  "reviewed_at_utc": "fixture-clock-only"}
        with TemporaryDirectory() as directory:
            attempt = Path(directory)
            (attempt / "analysis-report.json").write_text("{}\n")
            rows = [{"heavy_vehicle_components": [{"actor_id": 1}]},
                    {"heavy_vehicle_components": [{"actor_id": 2}]}]
            (attempt / "heavy_lane_sources.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in rows))
            with patch("delivery_audit.audit", return_value={"frames": 2}):
                with self.assertRaisesRegex(ValueError, "complete heavy-body participant history"):
                    physical.audit_saved(attempt, case, review, allow_fixture=True)

    def test_physical_case_events_and_missing_pixel_review(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        frames = [{"frame": 1, "time_s": 0.0, "minimum_clearance_m": 0.5,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": 0.5,
                                             "right_clearance_m": 0.5}]},
                  {"frame": 2, "time_s": 0.05, "minimum_clearance_m": -0.2,
                   "component_clearances": [{"actor_id": 205, "left_clearance_m": -0.2,
                                             "right_clearance_m": 1.2}]}]
        trace = [{"frame": 1, "time_s": 0.0, "position": {"x": 0.0, "y": 0.0}},
                 {"frame": 2, "time_s": 0.05, "position": {"x": 1.0, "y": 0.0}}]
        sources = {name: name for name in ("native_three_lane_survey.json",
                    "heavy_lane_sources.jsonl", "trace.jsonl", "video_frames.jsonl")}
        sources.update({name + ".mkv": name for name in physical.CAMERAS})
        decoded = {name: {"sha256": name, "decoded_frames": 2} for name in physical.CAMERAS}
        review = {"cameras": {name: {"source_sha256": name, "reviewed_frames": 2,
                     "frames": [{"video_frame": index, "required_markings_visible": True,
                                 "required_bodies_visible": True} for index in range(2)]}
                     for name in physical.CAMERAS}}

        def evaluate(suffix, *, passing=None, turn=None, rows=frames, pixels=review):
            case = prefix + suffix
            measurements = {"heavy_lane_footprint": {"value": {"frames": rows},
                            "sources": sources}}
            if passing is not None:
                measurements["passing_context"] = {"value": passing}
            if turn is not None:
                measurements["turn_preparation_context"] = {"value": turn}
            return physical.evaluate({"case_id": case, "measurements": measurements},
                    {"case_id": case, "source_join_verified": True, "frames": 2,
                     "four_camera_decode": decoded},
                    dict(pixels, case_id=case), trace)

        self.assertEqual(evaluate("unexcused_boundary_crossing")
                         ["physical_checks"]["maneuver"]["status"], "met")
        self.assertEqual(evaluate("within_marked_lane")
                         ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": False})
            ["physical_checks"]["maneuver"]["status"], "not_met")
        self.assertEqual(evaluate("passing_boundary_crossing", passing={
            "overtaken_actor_ids": [306], "order_reversal_observed": True})
            ["physical_checks"]["maneuver"]["status"], "met")
        turn = {"source_frame_count": 2, "turn_plan": {"requested_movement": "turn",
                                                "direction": "right"}}
        self.assertEqual(evaluate("lawful_turn_preparation_boundary_crossing", turn=turn)
                         ["physical_checks"]["maneuver"]["status"], "met")
        missing_review = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        missing_review["cameras"]["approach"]["frames"][0]["required_markings_visible"] = False
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=missing_review)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        incomplete_review = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        incomplete_review["cameras"]["approach"]["frames"] = review["cameras"]["approach"]["frames"][:1]
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=incomplete_review)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        wrong_frame = {"cameras": {name: dict(value) for name, value in review["cameras"].items()}}
        wrong_frame["cameras"]["overview"]["frames"] = [dict(row) for row in review["cameras"]["overview"]["frames"]]
        wrong_frame["cameras"]["overview"]["frames"][1]["video_frame"] = 0
        self.assertEqual(evaluate("unexcused_boundary_crossing", pixels=wrong_frame)
                         ["physical_checks"]["maneuver"]["status"], "unverified")
        bad = [dict(row) for row in frames]
        bad[1]["component_clearances"] = []
        with self.assertRaisesRegex(ValueError, "full heavy-body clearances"):
            evaluate("unexcused_boundary_crossing", rows=bad)

    def test_lifecycle_order_and_early_processing_for_all_selected_cases(self):
        prefix = "heldout__C305951__LVMC-11-18-030-B__heavy_vehicle_driver__"
        for suffix in ("within_marked_lane", "unexcused_boundary_crossing",
                       "passing_boundary_crossing",
                       "lawful_turn_preparation_boundary_crossing"):
            case = prefix + suffix
            with self.subTest(case=case, order="early"):
                rejected = lifecycle.run(case, out_of_order=True)
                self.assertEqual(rejected["status"], "rejected")
                self.assertIn("native-exit.json", rejected["reason"])
            with self.subTest(case=case, order="complete"):
                accepted = lifecycle.run(case)
                self.assertEqual(accepted["status"], "passed")
                self.assertEqual(accepted["events"], lifecycle.EVENTS)



if __name__ == "__main__":
    unittest.main()
