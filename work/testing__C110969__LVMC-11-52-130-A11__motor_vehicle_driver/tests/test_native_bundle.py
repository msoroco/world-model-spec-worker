import hashlib
import io
import json
import pathlib
import sys
import tempfile
import types
import unittest
from PIL import Image


BASE = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from native_bundle import capture_bundle
from native_map import PREFIX, SUFFIXES
from saved_delivery import audit
from analysis import finalize, write_recording_channels


class World:
    def __init__(self):
        self.frame = 100

    def get_map(self):
        return types.SimpleNamespace(name="DiagnosticTown",
                                     to_opendrive=lambda: "diagnostic OpenDRIVE")

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.frame += 1
        return self.frame


class Control:
    def __init__(self, throttle=0.0, brake=0.0):
        self.throttle = throttle
        self.brake = brake


class Ego:
    id = 17

    def __init__(self):
        self.controls = []

    def get_transform(self):
        return types.SimpleNamespace(x=8 + 14 * 0.3048 + 2.25,
                                     y=0.0, heading=180.0)

    def get_velocity(self):
        return types.SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def get_control(self):
        return Control()

    def apply_control(self, control):
        self.controls.append(control)


class NativeBundleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=pathlib.Path.cwd() / ".runtime-work")
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.map_path = self.root / "map-packet.json"
        self.map_path.write_text(json.dumps({
            "case_ids": sorted(PREFIX + suffix for suffix in SUFFIXES),
            "map_name": "DiagnosticTown",
            "opendrive_sha256": hashlib.sha256(b"diagnostic OpenDRIVE").hexdigest(),
            "geometry_provenance": "diagnostic CPU fixture only",
            "boundary_review_source_sha256": "a" * 64,
            "intersection_boundary_local_m": {
                "west": -8, "south": -8, "east": 8, "north": 8},
            "approach": "east", "route_waypoint_ids": [11, 12, 13],
            "local_transform_source_sha256": "b" * 64,
            "vehicle_length_m": 4.5, "vehicle_width_m": 1.8}))
        self.ego = Ego()
        png_stream = io.BytesIO()
        Image.new("RGB", (2, 2), (23, 41, 59)).save(png_stream, format="PNG")
        png_bytes = png_stream.getvalue()
        self.args = dict(
            map_packet_path=self.map_path, case_id=PREFIX + "stop_14ft",
            attempt_id="diagnostic-attempt", recording_id="diagnostic-recording",
            world_to_local=lambda t: (t.x, t.y, t.heading),
            read_camera=lambda name, frame: (frame, png_bytes),
            read_context=lambda frame: {"world_frame": frame,
                                        "participants": [], "directions": {}})

    def test_original_bundle_feeds_saved_audit(self):
        receipt = capture_bundle(World(), self.ego, self.root / "attempt", **self.args)
        self.assertEqual(receipt["frame_count"], 900)
        self.assertEqual(self.ego.controls[-1].brake, 1)
        result = audit(receipt["attempt_path"], allow_diagnostic=True)
        self.assertTrue(result["time_join"])
        self.assertEqual(result["decoded_original_images"], 3600)
        self.assertFalse(result["native_source"])
        self.assertFalse(result["physical_completion"])

    def test_camera_drift_brakes_and_keeps_incomplete_source(self):
        self.args["read_camera"] = lambda name, frame: (
            frame + 1, b"\x89PNG\r\n\x1a\n")
        with self.assertRaisesRegex(ValueError, "Camera frame drift"):
            capture_bundle(World(), self.ego, self.root / "attempt", **self.args)
        self.assertEqual(self.ego.controls[-1].brake, 1)
        self.assertFalse((self.root / "attempt" / "attempt.json").exists())

    def test_selected_analysis_joins_five_statutory_observations(self):
        from pathlib import Path
        sys.path.insert(0, str(Path.cwd() / "runtime/scenario_pipeline"))
        from worker_exchange.measurement_contract import verify_report
        stage = self.root / "selected"
        stage.mkdir()
        capture_bundle(World(), self.ego, stage / "original-attempt", **self.args)
        (stage / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n")
        report = finalize(stage, self.args["case_id"])
        plan = json.loads((BASE / "case-plan.json").read_text())
        description = plan["cases"][0]["recording_description"]
        evidence = write_recording_channels(stage, description)
        from batch_pipeline.validation import recording_evidence
        recording_evidence({"recording_description": description,
                            "recording_evidence": evidence}, description,
                           lambda relative: stage / relative)
        self.assertEqual(len(evidence), 8)
        contract = json.loads((BASE / "cases/stop_14ft/measurement-contract.json").read_text())
        values = verify_report(contract, report, stage)
        self.assertEqual(len(values), 5)
        self.assertAlmostEqual(values["observed_intersection_gap"]["value"]["minimum_halt_body_gap_m"], 14 * 0.3048)
        self.assertEqual(values["observed_traffic"]["value"]["necessity_judgment"],
                         "unresolved_from_original_traffic_geometry")
        (stage / "original-attempt/context.jsonl").unlink()
        with self.assertRaisesRegex(ValueError, "source missing|Missing required source"):
            finalize(stage, self.args["case_id"])


if __name__ == "__main__":
    unittest.main()
