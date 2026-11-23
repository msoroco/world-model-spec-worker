"""Synthetic source custody tests; fixture sources are never official evidence."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from analysis import build_report
from comparison_audit import audit
from delivery_audit import audit_attempt
from scene_construction import scene
from source_review import validate as validate_site


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path, value):
    path.write_text(value)
    return sha(path)


def fixture(root, *, bus_lane="east", green=("east",), moving=True, case_id=None):
    highway_hash = put(root / "synthetic-highway.txt", "synthetic public highway record\n")
    device_hash = put(root / "synthetic-device.txt", "synthetic green arrow over east lane\n")
    packet = {"review_status": "reviewed",
              "highway": {"source_path": "synthetic-highway.txt", "source_sha256": highway_hash,
                          "source_citation": "synthetic test fixture", "reviewer": "unit test only",
                          "status": "public_highway_reviewed", "highway_id": "fixture-highway"},
              "official_device": {"source_path": "synthetic-device.txt", "source_sha256": device_hash,
                                  "source_citation": "synthetic test fixture", "reviewer": "unit test only",
                                  "device_kind": "official_overhead_lane_signal",
                                  "symbol": "down_green_arrow", "faces_bus": True,
                                  "placement": "over_individual_lanes",
                                  "native_asset_blueprint_id": "fixture.signal",
                                  "dark_asset_blueprint_id": "fixture.dark",
                                  "native_display_state": {"attribute": "display_state",
                                                           "green_value": "down_green_arrow",
                                                           "dark_value": "dark",
                                                           "source_citation": "synthetic test fixture"},
                                  "governed_lane_ids": list(green)}}
    packet_hash = put(root / "reviewed-context.json", json.dumps(packet))
    acquisition = {"reviewed-context.json": packet_hash}
    channels = {name: [] for name in ("bus-body-history.jsonl", "lane-signal-history.jsonl",
                                      "camera-frame-map.jsonl")}
    for frame in range(3):
        t = frame / 20
        x = float(frame if moving else 0)
        y = 0 if bus_lane == "east" else 4
        payload = {"frame": frame, "elapsed_seconds": t}
        body = {**payload, "bus_footprint": [[x-1, y-1], [x+1, y-1],
                                               [x+1, y+1], [x-1, y+1]]}
        signal = {**payload, "highway_id": "fixture-highway",
                  "official_device_source_sha256": device_hash,
                  "faces_bus": True, "placement": "over_individual_lanes",
                  "lanes": [{"lane_id": "east", "direction": "bus_direction",
                             "lateral_bounds_m": [-2, 2],
                             "symbol": "down_green_arrow" if "east" in green else "dark"},
                            {"lane_id": "west", "direction": "bus_direction",
                             "lateral_bounds_m": [2, 6],
                             "symbol": "down_green_arrow" if "west" in green else "dark"}]}
        camera = {**payload, "camera_names": ["overview", "approach",
                                             "reference_corner", "driver_reference"]}
        for name, data, prefix in (("bus-body-history.jsonl", body, "body"),
                                   ("lane-signal-history.jsonl", signal, "signal"),
                                   ("camera-frame-map.jsonl", camera, "camera")):
            original = prefix + "-" + str(frame) + ".json"
            digest = put(root / original, json.dumps(data))
            acquisition[original] = digest
            channels[name].append({**data, "source_path": original, "source_sha256": digest})
    for name, rows in channels.items():
        acquisition[name] = put(root / name, "".join(json.dumps(row) + "\n" for row in rows))
    put(root / "acquisition.json", json.dumps(acquisition))
    if case_id:
        put(root / "scene.json", json.dumps(scene(case_id, "a" * 64)))
    return acquisition


def sealed_fixture(root):
    acquisition = fixture(root, case_id="green_selected_drive")
    put(root / "road.xodr", (ROOT / "candidate-green-road.xodr").read_text())
    put(root / "carla_recorder.log", "synthetic unit-test recorder placeholder\n")
    frames = [{"video_frame": i, "carla_frame": i, "native_frame": i, "time_s": i / 20}
              for i in range(3)]
    put(root / "video_frames.jsonl", "".join(json.dumps(row) + "\n" for row in frames))
    put(root / "trace.jsonl", "".join(json.dumps({"frame": i, "time_s": i / 20,
                                                   "position_m": [i, 0]}) + "\n"
                                      for i in range(3)))
    put(root / "sign-state-original.jsonl", "".join(json.dumps({"frame": i,
        "elapsed_seconds": i / 20, "heads": []}) + "\n" for i in range(3)))
    put(root / "controller-history.jsonl", "".join(json.dumps({"frame": i,
        "elapsed_seconds": i / 20, "requested_control": {"brake": 0, "throttle": 0.5}}) + "\n"
        for i in range(3)))
    for name in ("overview", "approach", "reference_corner", "driver_reference"):
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                        "-i", "color=c=green:s=64x64:r=20", "-frames:v", "3", "-c:v", "ffv1",
                        str(root / (name + ".mkv"))], check=True, capture_output=True)
    original_names = ("road.xodr", "trace.jsonl", "video_frames.jsonl", "carla_recorder.log",
                      "bus-body-history.jsonl", "lane-signal-history.jsonl",
                      "sign-state-original.jsonl", "camera-frame-map.jsonl",
                      "controller-history.jsonl", "reviewed-context.json",
                      "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv")
    for name in original_names:
        acquisition[name] = sha(root / name)
    put(root / "acquisition.json", json.dumps(acquisition))
    seal = {"format": "worker-sealed-capture", "provenance_kind": "synthetic_fixture",
            "diagnostic_fixture": True, "frames": 3,
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "restoration": {"restored": True},
            "encoder_exit_codes": {name: 0 for name in
                                   ("overview", "approach", "reference_corner", "driver_reference")},
            "sources": {name: sha(root / name) for name in acquisition}}
    put(root / "capture-seal.json", json.dumps(seal))


class SavedAnalysisTests(unittest.TestCase):
    def test_reviewed_native_display_mapping_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            packet_path = root / "reviewed-context.json"
            packet = json.loads(packet_path.read_text())
            self.assertEqual(validate_site(packet_path, source_root=root)["native_display_state"]["green_value"],
                             "down_green_arrow")
            packet["official_device"]["native_display_state"]["dark_value"] = "down_green_arrow"
            packet_path.write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "green/dark display"):
                validate_site(packet_path, source_root=root)

    def test_delivery_audit_diagnostic_positive_and_native_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sealed_fixture(root)
            report = audit_attempt(root, diagnostic=True)
            self.assertEqual(report["decoded_frames"], {name: 3 for name in
                             ("overview", "approach", "reference_corner", "driver_reference")})
            self.assertFalse(report["physical_acceptance_claimed"])
            with self.assertRaisesRegex(ValueError, "original Native acquisition required"):
                audit_attempt(root)
            (root / "lane-signal-history.jsonl").unlink()
            with self.assertRaisesRegex(ValueError, "source missing or changed"):
                audit_attempt(root, diagnostic=True)

    def test_pinned_saved_result_and_converter_channels_from_staged_fixture(self):
        repo = ROOT.parents[1]
        for kind in ("green_selected_drive", "adjacent_dark_drive",
                     "second_green_drive", "green_selected_stand"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                lane = "west" if kind in ("adjacent_dark_drive", "second_green_drive") else "east"
                green = ("east", "west") if kind == "second_green_drive" else ("east",)
                fixture(root, bus_lane=lane, green=green,
                        moving=kind != "green_selected_stand", case_id=kind)
                construction = json.loads((ROOT / "cases" / kind / "construction.json").read_text())
                put(root / "construction.json", json.dumps(construction))
                config = next(item["content"] for item in construction["files"]
                              if item["path"] == "config.json")
                put(root / "config.json", config)
                env = os.environ.copy()
                env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(repo / ".runtime-work/c147332-12a-runtime")
                env["PYTHONPATH"] = str(repo / "runtime/scenario_pipeline")
                env["PYTHONDONTWRITEBYTECODE"] = "1"
                completed = subprocess.run([sys.executable, str(ROOT / "analysis.py"),
                                            "--attempt", str(root), "--output",
                                            str(root / "analysis-report.json")],
                                           env=env, capture_output=True, text=True)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads((root / "result.json").read_text())
                self.assertEqual([check["matched"] for check in result["target_checks"]], [True, True])
                self.assertFalse(result["physical_acceptance_claimed"])
                self.assertFalse(result["maneuver_completed"])
                self.assertEqual(len(result["recording_evidence"]), 4)
                for item in result["recording_evidence"]:
                    self.assertTrue((root / item["reference"]).is_file())

    def test_pinned_saved_result_rejects_missing_original_channel(self):
        repo = ROOT.parents[1]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root, case_id="green_selected_drive")
            construction = json.loads((ROOT / "cases/green_selected_drive/construction.json").read_text())
            put(root / "construction.json", json.dumps(construction))
            config = next(item["content"] for item in construction["files"]
                          if item["path"] == "config.json")
            put(root / "config.json", config)
            (root / "lane-signal-history.jsonl").unlink()
            env = os.environ.copy()
            env["SCENARIO_PIPELINE_OUTPUT_ROOT"] = str(repo / ".runtime-work/c147332-12a-runtime")
            env["PYTHONPATH"] = str(repo / "runtime/scenario_pipeline")
            env["PYTHONDONTWRITEBYTECODE"] = "1"
            completed = subprocess.run([sys.executable, str(ROOT / "analysis.py"),
                                        "--attempt", str(root), "--output",
                                        str(root / "analysis-report.json")],
                                       env=env, capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Missing required source: lane-signal-history.jsonl",
                          completed.stderr)
            self.assertFalse((root / "result.json").exists())

    def test_source_bound_green_observation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            report = build_report(root)
            observed = report["measurements"]["green_arrow_bus_lane"]
            self.assertEqual(observed["permission_observed_frames"], [0, 1, 2])
            self.assertEqual(observed["bus_moving_frames"], [1, 2])
            self.assertFalse(report["physical_acceptance_claimed"])
            self.assertFalse(report["legal_verdict_claimed"])

    def test_changed_original_and_unreviewed_packet_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            (root / "body-1.json").write_text("tampered\n")
            with self.assertRaisesRegex(ValueError, "row source missing or changed"):
                build_report(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture(root)
            packet = json.loads((root / "reviewed-context.json").read_text())
            packet["review_status"] = "diagnostic"
            (root / "reviewed-context.json").write_text(json.dumps(packet))
            with self.assertRaisesRegex(ValueError, "review not completed"):
                build_report(root)

    def test_green_lane_and_acquisition_binding_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            acquisition = fixture(root)
            rows = [json.loads(s) for s in (root / "lane-signal-history.jsonl").read_text().splitlines()]
            rows[1]["lanes"][0]["symbol"] = "dark"
            acquisition["lane-signal-history.jsonl"] = put(
                root / "lane-signal-history.jsonl", "".join(json.dumps(row) + "\n" for row in rows))
            put(root / "acquisition.json", json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "observed green lanes differ"):
                build_report(root)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            acquisition = fixture(root)
            acquisition["reviewed-context.json"] = "0" * 64
            put(root / "acquisition.json", json.dumps(acquisition))
            with self.assertRaisesRegex(ValueError, "not bound"):
                build_report(root)

    def test_source_bound_comparison_pairs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b, c, d = (root / name for name in ("dark", "second", "drive", "stand"))
            for path in (a, b, c, d):
                path.mkdir()
            fixture(a, bus_lane="west", case_id="adjacent_dark_drive")
            fixture(b, bus_lane="west", green=("east", "west"), case_id="second_green_drive")
            fixture(c, case_id="green_selected_drive")
            fixture(d, moving=False, case_id="green_selected_stand")
            # The synthetic text is shared to exercise source binding only.
            self.assertTrue(audit(a, b, "second_green_arrow")["source_bound"])
            self.assertTrue(audit(c, d, "permission_without_motion")["source_bound"])
            with self.assertRaisesRegex(ValueError, "wrong exact comparison"):
                audit(b, a, "second_green_arrow")

    def test_comparison_rejects_changed_original_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b = root / "dark", root / "second"
            a.mkdir()
            b.mkdir()
            fixture(a, bus_lane="west", case_id="adjacent_dark_drive")
            fixture(b, bus_lane="west", green=("east", "west"), case_id="second_green_drive")
            source = b / "body-1.json"
            source.write_text("changed body")
            with self.assertRaisesRegex(ValueError, "row source missing or changed"):
                audit(a, b, "second_green_arrow")


if __name__ == "__main__":
    unittest.main()
