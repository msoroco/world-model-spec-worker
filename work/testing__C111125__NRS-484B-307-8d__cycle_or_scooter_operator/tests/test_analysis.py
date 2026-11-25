import hashlib
import importlib.util
import json
import sys
import unittest
from pathlib import Path

import test_signal_trial as signal_fixture


BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("c111125_8d_analysis", BASE / "analysis.py")
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        fixture = signal_fixture.SignalTrialTests("test_measure_original_cycles_and_reject_missing_readbacks")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.root = fixture.root
        case = "testing__C111125__NRS-484B-307-8d__cycle_or_scooter_operator__two_cycles_failed_detection"
        packet = fixture.packet("two_cycles_failed_detection", fixture.frames())
        site = fixture.site
        site["case_id"] = case
        source_dir = self.root / "source"
        source_dir.mkdir()
        for name in ("map", "device", "detector", "blueprint"):
            source = self.root / (name + ".json")
            target = source_dir / source.name
            source.rename(target)
            site[name + "_ref"]["path"] = "source/" + target.name
        for key, name in (("native_trace_ref", "native"), ("device_trace_ref", "device"),
                          ("detector_trace_ref", "detector")):
            source = self.root / packet[key]["path"]
            target = self.root / (name + ".json")
            source.rename(target)
            packet[key]["path"] = target.name
        (self.root / "native-site.json").write_text(json.dumps(site) + "\n")
        (self.root / "packet.json").write_text(json.dumps(packet) + "\n")
        (self.root / "config.json").write_text(json.dumps({
            "selected_case_id": case,
            "case_suffix": "two_cycles_failed_detection",
            "source_inventory": list(analysis.SOURCE_NAMES),
        }) + "\n")

    def test_selected_six_source_measurements(self):
        report = analysis.analyze_measurements(self.root)
        self.assertEqual(len(report["measurements"]), 6)
        self.assertTrue(report["measurements"]["antecedent_stop"]["value"]["prior_stop_observed"])
        self.assertEqual(report["measurements"]["complete_device_cycles"]["value"]["complete_device_cycles_before_entry"], 2)
        self.assertFalse(report["physical_acceptance_claimed"])
        self.assertFalse(report["legal_verdict_claimed"])
        for item in report["measurements"].values():
            self.assertEqual(set(item["sources"]), set(analysis.SOURCE_NAMES))
            for path, digest in item["sources"].items():
                self.assertEqual(hashlib.sha256((self.root / path).read_bytes()).hexdigest(), digest)

    def test_rejects_missing_and_rehashed_selected_source(self):
        source = self.root / "source/detector.json"
        source.write_text('{"detector_id":"another-loop"}\n')
        site_path = self.root / "native-site.json"
        site = json.loads(site_path.read_text())
        site["detector_ref"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
        site_path.write_text(json.dumps(site) + "\n")
        with self.assertRaisesRegex(ValueError, "causal link lacks original source binding"):
            analysis.analyze_measurements(self.root)
        source.unlink()
        with self.assertRaisesRegex(ValueError, "Missing required source: source/detector.json"):
            analysis.analyze_measurements(self.root)

    def prepare_900_frame_fixture(self):
        from importlib.util import spec_from_file_location, module_from_spec
        builder_spec = spec_from_file_location("c111125_8d_builder", BASE / "build_offline_draft.py")
        builder = module_from_spec(builder_spec)
        builder_spec.loader.exec_module(builder)
        config_path = self.root / "config.json"
        config = json.loads(config_path.read_text())
        config["case"] = {"recording_description": builder.recording_description()}
        config_path.write_text(json.dumps(config) + "\n")
        frames = []
        for i in range(900):
            phase = ("red" if i < 100 else "green" if i < 200 else
                     "yellow" if i < 300 else "red" if i < 400 else
                     "green" if i < 500 else "yellow" if i < 600 else "red")
            frames.append({"frame": i, "timestamp_s": i / 20,
                           "subject_signal": "red", "cross_signal": phase,
                           "detector_occupied": True, "detector_output": False,
                           "ego_speed_mps": 0.0 if i < 600 else 1.0,
                           "ego_station_m": 0.0 if i < 600 else min(10.0, (i - 600) / 10),
                           "directed_participant_conflict": False})
        streams = {
            "native": {"frames": frames, "blueprint_class": "bicycle"},
            "device": {"frames": [{"frame": f["frame"], "subject_signal": f["subject_signal"],
                                   "cross_signal": f["cross_signal"]} for f in frames]},
            "detector": {"frames": [{"frame": f["frame"], "occupied": True, "output": False}
                                     for f in frames]},
        }
        packet_path = self.root / "packet.json"
        packet = json.loads(packet_path.read_text())
        packet["frames"] = frames
        for name, data in streams.items():
            path = self.root / (name + ".json")
            path.write_text(json.dumps(data, separators=(",", ":")) + "\n")
            packet[name + "_trace_ref"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        packet_path.write_text(json.dumps(packet, separators=(",", ":")) + "\n")
        (self.root / "trace.jsonl").write_text("".join(json.dumps({"frame": i,
            "time_s": i / 20, "position_m": [f["ego_station_m"], 0, 0],
            "speed_mps": f["ego_speed_mps"]}) + "\n" for i, f in enumerate(frames)))
        (self.root / "video_frames.jsonl").write_text("".join(json.dumps({
            "video_frame": i, "carla_frame": i, "native_frame": i,
            "time_s": i / 20}) + "\n" for i in range(900)))
        for camera in ("overview", "approach", "reference_corner", "driver_reference"):
            (self.root / (camera + ".mkv")).write_bytes(b"diagnostic-only-join-placeholder")
        (self.root / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")

    def test_900_frame_finalizer_joins_originals_and_writes_native_result(self):
        self.prepare_900_frame_fixture()
        sys.path.insert(0, str(BASE.parents[1] / "runtime" / "scenario_pipeline"))
        report = analysis.finalize(self.root)
        result = json.loads((self.root / "result.json").read_text())
        self.assertEqual(report["measured_values"]["complete_device_cycles_before_entry"], 2)
        self.assertEqual(result["provenance_kind"], "synthetic_fixture")
        self.assertEqual(len(result["recording_evidence"]), 8)
        self.assertTrue(all(row["matched"] for row in result["target_checks"]))
        self.assertFalse(result["physical_acceptance_claimed"])
        self.assertEqual(len((self.root / "recording-channel-0.jsonl").read_text().splitlines()), 900)
