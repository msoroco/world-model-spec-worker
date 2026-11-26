import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "delivery_measure.py"
spec = importlib.util.spec_from_file_location("delivery_measure", SOURCE)
measure = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = measure
spec.loader.exec_module(measure)


def trace(case_id="case-open", act="open", side="left", gap=0.05):
    context = {"map_sha256": "map-hash", "survey_sha256": "survey-hash",
               "loading_site_id": "crest-loading", "parked_vehicle_id": "parked",
               "driver_id": "driver", "passing_vehicle_id": "traffic",
               "traffic_route_id": "route", "camera_contract_id": "four-view"}
    frames = []
    for frame_id in (100, 101, 102):
        frames.append({"frame_id": frame_id,
                       "sim_time_s": frame_id / 20,
                       "camera_frames": {v: frame_id for v in ("front", "rear", "left", "right")},
                       "selected_driver_id": "driver",
                       "observed_act": act if frame_id == 101 else "none",
                       "act_side": side if frame_id == 101 else None,
                       "passing_center_xy": [frame_id - 101, 1.5],
                       "passing_speed_mps": 4.0,
                       "act_envelope_xy": [[0, 1], [1, 1]],
                       "passing_body_xy": [[0, 1 + gap], [1, 1 + gap]],
                       "passing_response": {"brake": 0.2, "acceleration_mps2": -0.5}})
    return {"source_kind": "native_original", "case_id": case_id,
            "sample_rate_hz": 20, "fixed_context": context,
            "parked_center_xy": [0, 0], "parked_heading_xy": [1, 0],
            "frames": frames}


class DeliveryMeasureTests(unittest.TestCase):
    def test_original_frame_measurement_and_no_legal_verdict(self):
        result = measure.measure(trace(), expected_case_id="case-open",
                                 expected_act="open", expected_side="left")
        self.assertAlmostEqual(result["minimum_body_gap_m"], 0.05)
        self.assertTrue(result["act_on_closest_side"])
        self.assertEqual(result["legal_interference"], "unresolved_judgment")
        self.assertEqual(result["act_frame_ids"], [101])

    def test_unclosed_outline_closing_edge_is_measured(self):
        original = trace()
        frame = original["frames"][1]
        frame["act_envelope_xy"] = [[0, 0], [1, 0], [1, 1], [0, 1]]
        frame["passing_body_xy"] = [[-2, 0.4], [-1, 0.4], [-1, 0.6], [-2, 0.6]]
        measured = measure.measure(original, expected_case_id="case-open",
                                   expected_act="open", expected_side="left")
        self.assertAlmostEqual(measured["minimum_body_gap_m"], 1.0)
        frame["act_envelope_xy"].append([0, 0])
        closed = measure.measure(original, expected_case_id="case-open",
                                 expected_act="open", expected_side="left")
        self.assertEqual(closed["minimum_body_gap_m"], measured["minimum_body_gap_m"])

    def test_contained_body_has_zero_gap(self):
        original = trace()
        frame = original["frames"][1]
        frame["act_envelope_xy"] = [[0, 0], [3, 0], [3, 3], [0, 3]]
        frame["passing_body_xy"] = [[1, 1], [2, 1], [2, 2], [1, 2]]
        measured = measure.measure(original, expected_case_id="case-open",
                                   expected_act="open", expected_side="left")
        self.assertEqual(measured["minimum_body_gap_m"], 0.0)

    def test_sealed_source_rejects_stale_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "original.json"
            data = json.dumps(trace()).encode()
            path.write_bytes(data)
            self.assertEqual(measure.read_sealed_trace(path, hashlib.sha256(data).hexdigest())["case_id"],
                             "case-open")
            path.write_bytes(data + b" ")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                measure.read_sealed_trace(path, hashlib.sha256(data).hexdigest())

    def test_saved_only_command_emits_measurement(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "native.json"
            output = Path(directory) / "measurement.json"
            source.write_text(json.dumps(trace()), encoding="utf-8")
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            command = [sys.executable, str(SOURCE), "--source", str(source),
                       "--source-sha256", digest, "--case-id", "case-open",
                       "--act", "open", "--side", "left", "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(json.loads(output.read_text())["act_frame_ids"], [101])
            self.assertNotEqual(subprocess.run(command[:5] + ["0" * 64] + command[6:],
                                               capture_output=True).returncode, 0)

    def test_missing_original_sources_fail_closed(self):
        for mutation in (lambda x: x["frames"][1]["camera_frames"].pop("rear"),
                         lambda x: x["frames"][1].pop("passing_body_xy"),
                         lambda x: x["frames"][1].pop("passing_response"),
                         lambda x: x["frames"][1].update(frame_id=103),
                         lambda x: x["frames"][1].update(sim_time_s=99),
                         lambda x: x["frames"][1].update(selected_driver_id="someone-else"),
                         lambda x: x["frames"][1].update(observed_act="none"),
                         lambda x: x.update(source_kind="synthetic")):
            source = trace()
            mutation(source)
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                measure.measure(source, expected_case_id="case-open",
                                expected_act="open", expected_side="left")

    def test_comparison_isolation(self):
        a = measure.measure(trace(), expected_case_id="case-open",
                            expected_act="open", expected_side="left")
        b = measure.measure(trace("case-clear", gap=2.0), expected_case_id="case-clear",
                            expected_act="open", expected_side="left")
        checked = measure.audit_pair(a, b, deliberate_difference="body_gap_m")
        self.assertTrue(checked["fixed_context_checked"])
        bad = copy.deepcopy(b)
        bad["fixed_context"]["map_sha256"] = "other-map"
        with self.assertRaisesRegex(ValueError, "context changed"):
            measure.audit_pair(a, bad, deliberate_difference="body_gap_m")
        with self.assertRaisesRegex(ValueError, "no measured difference"):
            measure.audit_pair(a, {**b, "minimum_body_gap_m": a["minimum_body_gap_m"]},
                               deliberate_difference="body_gap_m")
        altered_speed = copy.deepcopy(b)
        altered_speed["passing_history"][1]["speed_mps"] = 9.0
        with self.assertRaisesRegex(ValueError, "speed history changed"):
            measure.audit_pair(a, altered_speed, deliberate_difference="body_gap_m")
        altered_timing = copy.deepcopy(b)
        altered_timing["act_frame_ids"] = [102]
        with self.assertRaisesRegex(ValueError, "act timing changed"):
            measure.audit_pair(a, altered_timing, deliberate_difference="body_gap_m")

    def test_act_and_side_comparisons(self):
        near = measure.measure(trace(), expected_case_id="case-open",
                               expected_act="open", expected_side="left")
        far = measure.measure(trace("case-far", side="right"), expected_case_id="case-far",
                              expected_act="open", expected_side="right")
        board = measure.measure(trace("case-board", act="board"), expected_case_id="case-board",
                                expected_act="board", expected_side="left")
        self.assertEqual(measure.audit_pair(near, far, deliberate_difference="act_side")
                         ["deliberate_difference"], "act_side")
        self.assertEqual(measure.audit_pair(near, board, deliberate_difference="observed_act")
                         ["deliberate_difference"], "observed_act")
        with self.assertRaises(ValueError):
            measure.audit_pair(near, far, deliberate_difference="observed_act")
        changed_route = copy.deepcopy(far)
        changed_route["passing_history"][1]["center_xy"][0] += 1.0
        with self.assertRaisesRegex(ValueError, "trajectory changed"):
            measure.audit_pair(near, changed_route, deliberate_difference="act_side")
        changed_route = copy.deepcopy(board)
        changed_route["passing_history"][1]["body_xy"][0][0] += 1.0
        with self.assertRaisesRegex(ValueError, "trajectory changed"):
            measure.audit_pair(near, changed_route, deliberate_difference="observed_act")

    def test_source_pair_audit_remeasures_and_rejects_stale_source(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in ("near.json", "clear.json")]
            for path, source in zip(paths, (trace(), trace("case-clear", gap=2.0))):
                path.write_text(json.dumps(source), encoding="utf-8")
            hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
            arguments = (paths[0], hashes[0], "case-open", "open", "left",
                         paths[1], hashes[1], "case-clear", "open", "left", "body_gap_m")
            result = measure.audit_source_pair(*arguments)
            self.assertEqual(result["source_sha256"], hashes)
            paths[1].write_text(json.dumps(trace("case-clear", gap=3.0)), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                measure.audit_source_pair(*arguments)

    def test_saved_comparison_command_checks_exact_plan_and_source_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            plan = base / "plan.json"
            plan.write_text(json.dumps({"comparisons": [{"comparison_id": "door_side",
                                                          "case_ids": ["case-open", "case-far"]}]}))
            sources = []
            for case_id, side in (("case-open", "left"), ("case-far", "right")):
                path = base / (case_id + ".json")
                path.write_text(json.dumps(trace(case_id, side=side)))
                sources.append({"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                "case_id": case_id, "act": "open", "side": side})
            spec_path, output = base / "spec.json", base / "comparison.json"
            spec = {"comparison_id": "door_side", "sources": sources}
            spec_path.write_text(json.dumps(spec))
            command = [sys.executable, str(SOURCE.with_name("compare_saved.py")),
                       "--plan", str(plan), "--spec", str(spec_path),
                       "--expected-comparison-id", "door_side", "--output", str(output)]
            self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(json.loads(output.read_text())["pair_audits"][0]
                             ["deliberate_difference"], "act_side")
            mismatch = command.copy()
            mismatch[mismatch.index("door_side")] = "selected_act"
            rejected = subprocess.run(mismatch, capture_output=True, text=True)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("comparison ID differs from dispatched queue row", rejected.stderr)
            spec["sources"] = list(reversed(sources))
            spec_path.write_text(json.dumps(spec))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            spec["sources"] = sources
            spec["sources"][1] = {**sources[1], "sha256": "0" * 64}
            spec_path.write_text(json.dumps(spec))
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_queue_comparison_commands_bind_exact_ids(self):
        proposal = json.loads((SOURCE.parent / "gpu-queue-proposal.json").read_text())
        for row in proposal["comparison_audit_commands"]:
            self.assertIn("--expected-comparison-id " + row["comparison_id"], row["command"])


if __name__ == "__main__":
    unittest.main()
