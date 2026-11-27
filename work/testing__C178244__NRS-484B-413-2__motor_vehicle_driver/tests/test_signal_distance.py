import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest

SCRATCH = Path.cwd() / ".runtime-work" / "c178244-signal-tests"
SCRATCH.mkdir(parents=True, exist_ok=True)

SPEC = importlib.util.spec_from_file_location("signal_distance", Path(__file__).resolve().parents[1] / "signal_distance.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def packet(start=0, district="business", direction="left", case_id="a", step_m=1.0):
    samples = []
    for i in range(30):
        samples.append({"frame": i, "time_s": i / 20, "x_m": i * step_m, "y_m": 0.0,
                        "signal": direction if i >= start else "off",
                        "light_source": "vehicle_light_state_readback"})
    return {"format": "original-signal-history-v1", "fps": 20,
            "sealed_result_sha256": "a" * 64, "frame_map_sha256": "b" * 64,
            "original_trace_sha256": "1" * 64,
            "original_video_sha256": "2" * 64,
            "signal_source": "vehicle_light_state_readback",
            "position_source": "native_actor_transform", "turn_onset_source": "native_lane_deviation",
            "district_class": district, "district_source": "reviewed_frontage_packet",
            "turn_direction": direction, "turn_onset_frame": 29, "samples": samples,
            "weather": "rain", "case_id": case_id, "route_sha256": "c" * 64,
            "map_sha256": "d" * 64, "camera_plan_sha256": "e" * 64,
            "duration_frames": 900, "ego_blueprint": "vehicle.test",
            "other_vehicle_plan_sha256": "f" * 64}


def write_sources(root, p):
    values = {"sealed_result": {"source": "sealed", "case_id": p["case_id"],
                                 "turn_direction": p["turn_direction"],
                                 "original_trace_sha256": p["original_trace_sha256"],
                                 "original_video_sha256": p["original_video_sha256"]},
              "frame_map": {"frames": [{"frame": row["frame"], "time_s": row["time_s"]}
                                       for row in p["samples"]]},
              "light_readback": {"samples": p["samples"]},
              "turn_onset": {"turn_onset_frame": p["turn_onset_frame"],
                             "turn_direction": p["turn_direction"]},
              "district_context": {k: p[k] for k in ("district_class", "district_source", "weather")}}
    p["source_files"] = {}
    for name, value in values.items():
        path = root / (name + ".json")
        path.write_text(json.dumps(value) + "\n")
        p["source_files"][name] = {"path": path.name, "sha256": sha256(path.read_bytes()).hexdigest()}
    p["sealed_result_sha256"] = p["source_files"]["sealed_result"]["sha256"]
    p["frame_map_sha256"] = p["source_files"]["frame_map"]["sha256"]


class SignalDistanceTest(unittest.TestCase):
    def test_measured_continuous_not_commanded(self):
        p = packet(start=4)
        p["commanded_signal_start_frame"] = 0
        value = mod.measure(p)
        self.assertEqual(value["continuous_start_frame"], 4)
        self.assertAlmostEqual(value["continuous_distance_m"], 25)
        self.assertEqual(value["statutory_reference_ft"], 100)

    def test_last_interruption_resets_distance(self):
        p = packet()
        p["samples"][18]["signal"] = "off"
        self.assertEqual(mod.measure(p)["continuous_start_frame"], 19)

    def test_other_area_reference(self):
        self.assertEqual(mod.measure(packet(district="other"))["statutory_reference_ft"], 300)

    def test_numeric_probe_below_at_above_100_feet(self):
        for delta_ft in (-1, 0, 1):
            with self.subTest(delta_ft=delta_ft):
                p = packet(step_m=(100 + delta_ft) * mod.METRES_PER_FOOT / 29)
                self.assertAlmostEqual(mod.measure(p)["continuous_distance_ft"], 100 + delta_ft)

    def test_numeric_probe_below_at_above_300_feet(self):
        for delta_ft in (-1, 0, 1):
            with self.subTest(delta_ft=delta_ft):
                p = packet(district="other", step_m=(300 + delta_ft) * mod.METRES_PER_FOOT / 29)
                self.assertAlmostEqual(mod.measure(p)["continuous_distance_ft"], 300 + delta_ft)

    def test_both_turn_directions(self):
        self.assertEqual(mod.measure(packet(direction="right"))["turn_direction"], "right")
        self.assertEqual(mod.measure(packet(direction="left"))["turn_direction"], "left")

    def test_reject_missing_original_sources(self):
        for key in ("sealed_result_sha256", "frame_map_sha256", "turn_onset_source",
                    "district_source", "original_trace_sha256", "original_video_sha256"):
            with self.subTest(key=key):
                p = packet()
                p[key] = ""
                with self.assertRaises(mod.EvidenceError):
                    mod.measure(p)

    def test_reject_command_as_readback(self):
        p = packet()
        p["samples"][2]["light_source"] = "controller_command"
        with self.assertRaisesRegex(mod.EvidenceError, "command substituted"):
            mod.measure(p)

    def test_reject_nonconsecutive_or_bad_time(self):
        p = packet()
        p["samples"][3]["frame"] = 5
        with self.assertRaisesRegex(mod.EvidenceError, "nonconsecutive"):
            mod.measure(p)
        p = packet()
        p["samples"][3]["time_s"] = 0.3
        with self.assertRaisesRegex(mod.EvidenceError, "20 Hz"):
            mod.measure(p)

    def test_reject_absent_onset_light(self):
        p = packet()
        p["samples"][29]["signal"] = "off"
        with self.assertRaisesRegex(mod.EvidenceError, "absent at turn onset"):
            mod.measure(p)

    def test_comparison_fixed_conditions_and_difference(self):
        a = packet(case_id="a")
        b = packet(start=10, case_id="b")
        result = mod.audit_comparison(a, b, "signal_activation_distance")
        self.assertEqual(result["case_ids"], ["a", "b"])
        b["weather"] = "clear"
        with self.assertRaisesRegex(mod.EvidenceError, "weather"):
            mod.audit_comparison(a, b, "signal_activation_distance")

    def test_comparison_rejects_no_measured_difference(self):
        with self.assertRaisesRegex(mod.EvidenceError, "not measured"):
            mod.audit_comparison(packet(case_id="a"), packet(case_id="b"), "signal_activation_distance")

    def test_source_inventory_checks_file_bytes_and_missing_source(self):
        p = packet()
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            self.assertEqual(len(mod.verify_source_bindings(p, root)), 5)
            (root / "light_readback.json").write_text("changed\n")
            with self.assertRaisesRegex(mod.EvidenceError, "stale source hash"):
                mod.verify_source_bindings(p, root)
            (root / "light_readback.json").unlink()
            with self.assertRaisesRegex(mod.EvidenceError, "missing source file"):
                mod.verify_source_bindings(p, root)

    def test_source_inventory_rejects_traversal(self):
        p = packet()
        p["source_files"] = {"sealed_result": {"path": "../elsewhere", "sha256": "a" * 64}}
        with TemporaryDirectory(dir=SCRATCH) as temp:
            with self.assertRaisesRegex(mod.EvidenceError, "escapes root"):
                mod.verify_source_bindings(p, Path(temp))

    def test_source_inventory_rejects_rebound_packet_values(self):
        p = packet()
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            p["samples"][4]["signal"] = "off"
            with self.assertRaisesRegex(mod.EvidenceError, "disagree with source"):
                mod.verify_source_bindings(p, root)
            p = packet()
            write_sources(root, p)
            p["turn_onset_frame"] = 28
            with self.assertRaisesRegex(mod.EvidenceError, "turn onset disagrees"):
                mod.verify_source_bindings(p, root)

    def test_resealed_frame_map_disagreement_rejected(self):
        p = packet()
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            frame_path = root / "frame_map.json"
            frame_map = json.loads(frame_path.read_text())
            frame_map["frames"][10]["time_s"] += 0.05
            frame_path.write_text(json.dumps(frame_map) + "\n")
            digest = sha256(frame_path.read_bytes()).hexdigest()
            p["source_files"]["frame_map"]["sha256"] = digest
            p["frame_map_sha256"] = digest
            with self.assertRaisesRegex(mod.EvidenceError, "frame map disagrees"):
                mod.verify_source_bindings(p, root)

    def test_relabelled_turn_direction_rejected_by_original_sources(self):
        p = packet(direction="left")
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            p["turn_direction"] = "right"
            with self.assertRaisesRegex(mod.EvidenceError, "sealed result turn direction"):
                mod.verify_source_bindings(p, root)
            sealed = root / "sealed_result.json"
            sealed.write_text(json.dumps({"source": "sealed", "case_id": p["case_id"],
                                          "turn_direction": "right",
                                          "original_trace_sha256": p["original_trace_sha256"],
                                          "original_video_sha256": p["original_video_sha256"]}) + "\n")
            digest = sha256(sealed.read_bytes()).hexdigest()
            p["source_files"]["sealed_result"]["sha256"] = digest
            p["sealed_result_sha256"] = digest
            with self.assertRaisesRegex(mod.EvidenceError, "observed turn direction"):
                mod.verify_source_bindings(p, root)

    def test_rebound_original_recording_hash_rejected(self):
        p = packet()
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            p["original_trace_sha256"] = "3" * 64
            with self.assertRaisesRegex(mod.EvidenceError, "original recording binding disagrees"):
                mod.verify_source_bindings(p, root)
            p["original_trace_sha256"] = "1" * 64
            p["original_video_sha256"] = ""
            with self.assertRaisesRegex(mod.EvidenceError, "missing original recording binding"):
                mod.verify_source_bindings(p, root)

    def test_cli_reads_and_verifies_source_packet(self):
        p = packet()
        with TemporaryDirectory(dir=SCRATCH) as temp:
            root = Path(temp)
            write_sources(root, p)
            packet_file = root / "packet.json"
            packet_file.write_text(json.dumps(p))
            cmd = [sys.executable, str(Path(mod.__file__)), "--packet", str(packet_file), "--source-root", str(root)]
            good = subprocess.run(cmd, text=True, capture_output=True, check=True)
            self.assertAlmostEqual(json.loads(good.stdout)["continuous_distance_m"], 29)
            (root / "district_context.json").unlink()
            bad = subprocess.run(cmd, text=True, capture_output=True)
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("missing source file", bad.stderr)


if __name__ == "__main__":
    unittest.main()
