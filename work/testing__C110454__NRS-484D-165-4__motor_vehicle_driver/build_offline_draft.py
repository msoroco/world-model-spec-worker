"""Build three exact parked-headlamp diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "lamp_probe.py", "parking_geometry.py", "native_capture.py",
    "camera_recorder.py", "saved_lamps.py", "delivery_audit.py",
    "comparison_audit.py", "owned_capture.py",
)

RUNNER = '''"""Exact parked-headlamp bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from lamp_probe import CASE_MODES
from native_capture import VIEWS
from camera_recorder import PROFILE_DIMENSIONS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    entries = [row for row in plan["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    mode = case.removeprefix(config["assignment_id"] + "__")
    if mode not in CASE_MODES or entries[0]["requested_headlamp_mode"] != mode or config["requested_headlamp_mode"] != mode:
        raise ValueError("Requested lamp mode changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original 20 Hz interval changed")
    if config["cameras"] != list(VIEWS):
        raise ValueError("Four original camera views changed")
    if config["camera_dimensions"] != {view: list(PROFILE_DIMENSIONS[view]) for view in VIEWS}:
        raise ValueError("Original camera profile dimensions changed")
    if config["source_requirements"] != ["reviewed_site", "actor_state", "camera_frame_map", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-packet")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic parked-headlamp bundle passed: " + case)
        return
    if not args.output_dir or not args.site_packet:
        raise ValueError("Reviewed Native intersection site and parked actor packet required")
    packet = json.loads(Path(args.site_packet).read_text(encoding="utf-8"))
    if (packet.get("case_id") != case or packet.get("diagnostic_fixture") is not False or
            not packet.get("parking_source_ref") or not packet.get("intersection_source_ref")):
        raise ValueError("Reviewed Native site case or provenance differs")
    import carla
    from owned_capture import capture_owned

    def transform(spec):
        return carla.Transform(
            carla.Location(x=spec["x_m"], y=spec["y_m"], z=spec["z_m"]),
            carla.Rotation(pitch=spec.get("pitch_deg", 0.0),
                           yaw=spec.get("yaw_deg", 0.0),
                           roll=spec.get("roll_deg", 0.0)))

    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    capture_owned(client, args.site_packet, args.output_dir, case_id=case,
                  mode=case.rsplit("__", 1)[-1], transform_factory=transform,
                  control_factory=carla.VehicleControl,
                  light_enum=carla.VehicleLightState)


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed Native intersection"):
                runner.main()

    def test_live_entrypoint_binds_owned_capture(self):
        case = runner.check()
        fake_carla = types.SimpleNamespace(
            Client=MagicMock(), Location=MagicMock(), Rotation=MagicMock(),
            Transform=MagicMock(), VehicleControl=MagicMock(),
            VehicleLightState=object())
        with tempfile.TemporaryDirectory() as directory:
            packet = Path(directory) / "site.json"
            packet.write_text(json.dumps({
                "case_id": case, "diagnostic_fixture": False,
                "parking_source_ref": "reviewed-parking-source",
                "intersection_source_ref": "reviewed-intersection-source"}) + "\\n")
            args = ["runner.py", "--site-packet", str(packet),
                    "--output-dir", str(Path(directory) / "attempt")]
            with patch.dict(sys.modules, {"carla": fake_carla}), \\
                    patch("owned_capture.capture_owned") as capture, \\
                    patch("sys.argv", args):
                runner.main()
            capture.assert_called_once()
            self.assertEqual(capture.call_args.kwargs["case_id"], case)
            self.assertEqual(capture.call_args.kwargs["mode"], case.rsplit("__", 1)[-1])
            packet.write_text(json.dumps({"case_id": "wrong", "diagnostic_fixture": False}) + "\\n")
            with patch.dict(sys.modules, {"carla": fake_carla}), \\
                    patch("owned_capture.capture_owned") as capture, \\
                    patch("sys.argv", args):
                with self.assertRaisesRegex(ValueError, "provenance differs"):
                    runner.main()
            capture.assert_not_called()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    rows = []
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484D-165-4", "cell_id": "C110454",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "requested_headlamp_mode": item["requested_headlamp_mode"],
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "camera_dimensions": {"overview": [1920, 1080], "approach": [1280, 720],
                                  "reference_corner": [1280, 720], "driver_reference": [1280, 720]},
            "source_requirements": ["reviewed_site", "actor_state", "camera_frame_map", "original_camera_media"],
            "required_atoms": [], "diagnostic_only": True,
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": {"status": "diagnostic_only_site_and_emission_review_pending", "channels": config["cameras"]},
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": "Parking footprint and actual headlamp emission/aim visibility need reviewed Native measurement; no source-verified fallback selected"}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_site_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact parked-headlamp diagnostic constructions")


if __name__ == "__main__":
    build()
