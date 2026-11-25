"""Build five exact diagnostic sidewalk-bypass constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "geometry.py", "native_construction.py", "native_walking.py", "native_source_packet.py",
    "native_readback.py", "native_actor_adapter.py", "native_camera_capture.py", "native_camera_rig.py", "native_attempt.py",
    "native_bound_attempt.py",
    "pedestrian_core_capture.py", "native_publication.py", "saved_finalizer.py",
    "saved_measurement.py", "analysis.py", "delivery_audit.py", "comparison_audit.py",
    "compare_saved.py",
)

RUNNER = '''"""Exact sidewalk-bypass diagnostic bundle entrypoint."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from geometry import construct, audit_design
from native_walking import FPS


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    plan_data = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_data).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    case = config["selected_case_id"]
    entries = [x for x in json.loads(plan_data)["cases"] if x["case_id"] == case]
    if len(entries) != 1 or not case.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact case missing")
    if config["construction_parameters"] != entries[0]["construction_parameters"]:
        raise ValueError("Case parameters changed")
    if config["rate_hz"] != FPS or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original frame contract changed")
    if config["cameras"] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Four-camera contract changed")
    p = config["construction_parameters"]
    scene = construct(case, direction=p["direction"], area_blocked=p["area_blocked"],
                      sidewalk_end=float(p["sidewalk_end_m"]), obstruction_kind=p["obstruction_kind"])
    result = audit_design(scene)
    if result["designated_lane_used"] != p["area_blocked"]:
        raise ValueError("Bicycle-lane condition changed")
    if p["obstruction_kind"] == "missing_section" and not scene.missing_sections:
        raise ValueError("Missing sidewalk surface not constructed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic sidewalk-bypass bundle passed: " + case)
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("Native output and host/port required")
    source_name = os.environ.get("SCENARIO_PEDESTRIAN_SOURCE_ROOT")
    if not source_name:
        raise ValueError("reviewed original hill-crest source root required")
    source = Path(source_name).resolve()
    output = Path(args.output_dir).resolve()
    if not source.is_dir() or not output.is_dir() or source == output:
        raise ValueError("reviewed source/output roots invalid")
    names = ("site-survey.json", "camera-profile.json", "traffic-plan.json")
    for name in names:
        original = source / name
        target = output / name
        if not original.is_file() or target.exists():
            raise ValueError("missing or colliding original source: " + name)
        shutil.copyfile(original, target)
        if hashlib.sha256(original.read_bytes()).digest() != hashlib.sha256(target.read_bytes()).digest():
            raise ValueError("original source changed while copying")
    import carla
    from native_bound_attempt import run_bound_attempt
    from native_publication import publish_original
    from worker_exchange import world_restore
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    plan = json.loads((output / "case-plan.json").read_text())
    run_bound_attempt(client, carla, plan, case, output / names[0],
                      output / names[1], output / names[2], output,
                      restore_api=world_restore)
    publish_original(output, case)


if __name__ == "__main__":
    main()
'''

TEST = '''import json
from pathlib import Path
import unittest
from unittest.mock import patch
import runner


class BundleTests(unittest.TestCase):
    def test_exact_constructed_geometry(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(runner.check(), json.loads((root / "config.json").read_text())["selected_case_id"])

    def test_refuses_unsurveyed_native_capture(self):
        with patch("sys.argv", ["runner.py", "--output-dir", "."]):
            with self.assertRaisesRegex(ValueError, "Native output and host/port"):
                runner.main()

    def test_refuses_missing_reviewed_source(self):
        with patch("sys.argv", ["runner.py", "--output-dir", ".", "--host", "127.0.0.1", "--port", "2000"]), patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(ValueError, "reviewed original hill-crest source"):
                runner.main()


if __name__ == "__main__":
    unittest.main()
'''

RECORDING_DESCRIPTION = {
    "channels": [{
        "name": "pedestrian_body_center_xy_m", "unit": "structured",
        "method": "Same-frame original Native walker body, Core graph and four-camera join",
        "time_window": "all 900 original Native frames", "reference_frame": "reviewed Native map world XY",
        "uncertainty": "Original geometry, visibility and legal due care require reviewed source",
        "sampling_rate_hz": 20,
        "unit_views": [{"unit": "m", "fields": {"/value/x": "m", "/value/y": "m"}}],
    }, {
        "name": "nearest_traffic_distance_m", "unit": "m",
        "method": "Original walker and surveyed traffic actor centers by frame",
        "time_window": "all 900 original Native frames", "reference_frame": "reviewed Native map world XY",
        "uncertainty": "Actor center separation does not establish due care",
        "sampling_rate_hz": 20,
    }],
    "context_inputs": [{
        "name": "source_provenance", "unit": "metadata",
        "method": "SHA-256 retained site survey, source packet and Core graph capture",
    }],
    "limitations": ["Diagnostic geometry cannot establish physical or legal acceptance."],
}


def build():
    plan_data = (HERE / "case-plan.json").read_bytes()
    plan = json.loads(plan_data)
    rows = []
    for item in plan["cases"]:
        case = item["case_id"]
        if not case.startswith(AID + "__"):
            raise ValueError("Foreign case")
        suffix = case.removeprefix(AID + "__")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-297-6", "cell_id": "C104081",
            "actor": "pedestrian", "selected_case_id": case,
            "plan_sha256": hashlib.sha256(plan_data).hexdigest(),
            "construction_parameters": item["construction_parameters"],
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "requested_speed_mps": 1.4,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "required_atoms": [], "diagnostic_only": True,
            "recording_description": RECORDING_DESCRIPTION,
        }
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": plan_data.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": RECORDING_DESCRIPTION,
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "measurement_contract": "measurement-contract-" + suffix + ".json",
                     "measurement_procedure": {"entrypoint": "analysis.py"},
                     "candidate_risk": {"status": "physical", "reason": item["physical_risk_assessment"]["risk"]}})
    semantic_index = HERE / "proposals/semantic-index.json"
    manifest = {"assignment_id": AID,
                "status": "diagnostic_offline_only_original_survey_pending",
                "cases": rows}
    if semantic_index.is_file():
        manifest["semantic_index_sha256"] = hashlib.sha256(semantic_index.read_bytes()).hexdigest()
    (HERE / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print("built", len(rows), "exact sidewalk-bypass diagnostic constructions")


if __name__ == "__main__":
    build()
