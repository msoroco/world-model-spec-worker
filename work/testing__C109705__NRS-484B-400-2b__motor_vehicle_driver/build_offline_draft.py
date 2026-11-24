"""Build four exact left-turn departure diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "construction.py", "native_map.py", "native_capture.py", "native_camera_source.py",
    "native_ego_adapter.py", "native_seal.py", "native_publication.py",
    "departure_geometry.py", "saved_delivery.py", "saved_pixels.py",
    "finalize.py", "comparison_audit.py", "analysis.py",
)

RUNNER = '''"""Exact two-directional left-turn departure bundle preflight."""
import argparse
import hashlib
import json
import os
from pathlib import Path
from construction import SUFFIXES
from native_capture import CAMERAS
from native_capture import capture
from native_camera_source import NativeCameraSource
from native_ego_adapter import NativeEgoAdapter
from native_seal import seal
from native_publication import project, encode


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact plan source changed")
    case = config["selected_case_id"]
    entries = [row for row in json.loads(source)["cases"] if row["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case absent")
    suffix = case.removeprefix(config["assignment_id"] + "__")
    if suffix not in SUFFIXES or config["departure_centerline_kind"] != entries[0]["departure_centerline_kind"]:
        raise ValueError("Destination centerline convention changed")
    if config["departure_position_target"] != entries[0]["departure_position_target"]:
        raise ValueError("Departure target changed")
    if config["duration_s"] != 45 or config["rate_hz"] != 20 or config["frame_count"] != 900:
        raise ValueError("Original timebase changed")
    if config["cameras"] != list(CAMERAS):
        raise ValueError("Original camera profile changed")
    if config["required_sources"] != ["reviewed_map", "original_trace", "original_camera_index", "original_camera_media"]:
        raise ValueError("Original measurement sources changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--survey")
    parser.add_argument("--survey-sha256")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic left-turn departure bundle passed: " + case)
        return
    survey_arg = args.survey or os.environ.get("CARLA_MAP_PACKET")
    survey_sha = args.survey_sha256 or os.environ.get("CARLA_MAP_PACKET_SHA256")
    if not survey_arg or not survey_sha or not args.output_dir:
        raise ValueError("Reviewed original two-directional Native map and full-body/camera sources required")
    import carla
    from worker_exchange.native_output import seal_capture
    survey_path = Path(survey_arg)
    raw = survey_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != survey_sha:
        raise ValueError("reviewed survey packet hash differs")
    survey = json.loads(raw)
    source_name = survey.get("map_source_path")
    if not isinstance(source_name, str) or not source_name or Path(source_name).is_absolute() or ".." in Path(source_name).parts:
        raise ValueError("reviewed original map source path missing")
    map_source = survey_path.parent / source_name
    if hashlib.sha256(map_source.read_bytes()).hexdigest() != survey.get("source_sha256"):
        raise ValueError("reviewed original map source hash differs")
    client = carla.Client(args.host, args.port)
    client.set_timeout(10.0)
    output = Path(args.output_dir)
    try:
        world = client.get_world()
        previous = world.get_settings()
        if previous.synchronous_mode:
            raise ValueError("exclusive Native synchronous world ownership required")
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        try:
            adapter = NativeEgoAdapter(world, carla, survey_path, survey_sha, case_id=case)
            camera = NativeCameraSource(world, carla, survey_path, survey_sha,
                                        output / "original-cameras")
            receipt = capture(adapter, case, survey, map_source, output, camera_source=camera)
        finally:
            world.apply_settings(previous)
        if world.get_settings().synchronous_mode != previous.synchronous_mode:
            raise ValueError("Native world restoration differs")
        receipt.update(seal(output, case_id=case, survey_path=survey_path,
                            survey_sha256=survey_sha,
                            map_source_path=map_source, capture_receipt=receipt))
        receipt["survey_sha256"] = survey_sha
        receipt["physical_acceptance_claimed"] = False
        (output / "acquisition.json").write_text(json.dumps(receipt, indent=2) + "\\n")
        frames = project(output, survey)
        hashes = encode(output)
        seal_capture(output, frames=frames, restoration={"restored": True,
                     "method": "Native world settings restored and verified"},
                     errors=[], encoder_exit_codes={name: 0 for name in hashes},
                     context={"survey_sha256": survey_sha,
                              "original_map_sha256": receipt["original_map_sha256"],
                              "encoded_video_sha256": hashes})
    except BaseException as error:
        (output / "native-run-status.json").write_text(json.dumps({
            "errors": [type(error).__name__ + ": " + str(error)],
            "physical_acceptance_claimed": False}, indent=2) + "\\n")
        raise


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_case_preflight(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsourced_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Reviewed original two-directional"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''


def build():
    source = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(source)
    semantic = json.loads((HERE / "proposals/cases.json").read_text())
    descriptions = {entry["case_id"]: entry["recording_description"]
                    for entry in semantic["cases"] if entry["target_type"] != "baseline"}
    rows = []
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-400-2b", "cell_id": "C109705",
            "actor": "motor_vehicle_driver", "selected_case_id": case,
            "plan_sha256": hashlib.sha256(source).hexdigest(),
            "departure_centerline_kind": item["departure_centerline_kind"],
            "departure_position_target": item["departure_position_target"],
            "duration_s": 45, "rate_hz": 20, "frame_count": 900,
            "cameras": ["dash", "front", "left", "right"],
            "required_sources": ["reviewed_map", "original_trace", "original_camera_index", "original_camera_media"],
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
            "recording_description": descriptions[case],
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": "physical", "reason": "Native destination centerline and full-body departure require original survey/readback; no source-verified alternate selected"}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_sources_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact departure diagnostic constructions")


if __name__ == "__main__":
    build()
