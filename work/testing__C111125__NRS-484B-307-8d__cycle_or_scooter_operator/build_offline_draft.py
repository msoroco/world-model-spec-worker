"""Build exact bicycle red-signal diagnostic constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SOURCE_FILES = (
    "signal_trial.py", "native_capture.py", "native_runner.py", "saved_attempt.py", "analysis.py",
    "saved_media_audit.py", "comparison_audit.py",
)
VARIANTS = (
    "two_cycles_failed_detection", "one_cycle", "three_cycles", "signal_changes",
    "no_prior_stop", "fails_to_yield",
)


def recording_description():
    channels = (
        ("bicycle and rider identity", "original blueprint and rider source with Native actor readback"),
        ("official facing red signal", "original official device aspect history"),
        ("stop boundary and bicycle motion", "original body station and speed history"),
        ("applicable device cycles", "20 Hz original phase history"),
        ("detector zone and output", "source-bound original loop occupancy/output history"),
        ("signal-directed pedestrians and traffic", "original participant conflict history"),
        ("four synchronized camera views", "original Native RGB sensors"),
    )
    return {
        "channels": [{"name": name, "unit": "source observation", "sampling_rate_hz": 20,
                      "method": method, "time_window": "original 45-second episode",
                      "reference_frame": "same original Native frame and simulation time",
                      "uncertainty": "Physical device causality, rider visibility and right-of-way status await original-source review"}
                     for name, method in channels],
        "context_inputs": [{"name": "reviewed map, official device, detector, bicycle and rider authority",
                            "unit": "source record", "method": "SHA-256-sealed source packets and original Native readback"}],
        "limitations": ["The selected cell fixes straight movement; turns are not claimed.",
                        "Diagnostic fixture phases do not prove a detector fault or physical visibility."]}

RUNNER = '''"""Exact bicycle red-signal bundle preflight."""
import argparse
import hashlib
import json
from pathlib import Path
from native_capture import CAMERAS, PROFILE_SIZES


VARIANTS = {"two_cycles_failed_detection", "one_cycle", "three_cycles", "signal_changes", "no_prior_stop", "fails_to_yield"}


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
    if suffix not in VARIANTS or config["case_suffix"] != suffix:
        raise ValueError("Exact red-signal variant changed")
    if config["rate_hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original timebase changed")
    if config["cameras"] != list(CAMERAS) or config["camera_sizes"] != {k: list(v) for k, v in PROFILE_SIZES.items()}:
        raise ValueError("Original camera profile changed")
    if config["required_sources"] != ["map", "device", "detector", "bicycle_blueprint", "native_trace", "original_camera_media"]:
        raise ValueError("Original source requirements changed")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic bicycle red-signal bundle passed: " + case)
        return
    raise ValueError("Reviewed Native map/device/detector, bicycle rider and original camera capture required")


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
            with self.assertRaisesRegex(ValueError, "Reviewed Native map/device/detector"):
                runner.main()


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
        if suffix not in VARIANTS:
            raise ValueError("Unknown exact red-signal case")
        config = {
            "assignment_id": AID, "law_id": "NRS-484B-307-8d", "cell_id": "C111125",
            "actor": "cycle_or_scooter_operator", "selected_case_id": case,
            "case_suffix": suffix, "plan_sha256": hashlib.sha256(source).hexdigest(),
            "rate_hz": 20, "frame_count": 900, "duration_s": 45,
            "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
            "camera_sizes": {"overview": [1920, 1080], "approach": [1280, 720],
                             "reference_corner": [1280, 720], "driver_reference": [1280, 720]},
            "required_sources": ["map", "device", "detector", "bicycle_blueprint", "native_trace", "original_camera_media"],
            "source_inventory": ["native-site.json", "packet.json", "native.json", "device.json",
                                 "detector.json", "geometry.json", "source/map.json",
                                 "source/device.json", "source/detector.json", "source/blueprint.json"],
            "required_atoms": [], "diagnostic_only": True,
        }
        config["case"] = {"case_id": case, "recording_description": recording_description()}
        files = {name: (HERE / name).read_text() for name in SOURCE_FILES}
        files.update({"runner.py": RUNNER, "case-plan.json": source.decode(),
                      "config.json": json.dumps(config, indent=2) + "\n",
                      "tests/test_bundle.py": TEST})
        construction = {
            "law_id": config["law_id"], "cell_id": config["cell_id"],
            "actor": config["actor"], "case_id": case,
            "entrypoint": "runner.py", "diagnostic_only": True,
            "recording_description": recording_description(),
            "files": [{"path": path, "content": content} for path, content in files.items()],
        }
        output = HERE / ("construction-" + suffix + ".json")
        output.write_text(json.dumps(construction, indent=2) + "\n")
        rows.append({"case_id": case, "construction": output.name,
                     "construction_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                     "candidate_risk": {"status": item["physical_risk_assessment"]["status"],
                                        "reason": item["physical_risk_assessment"]["risk"]}})
    (HERE / "execution-manifest.draft.json").write_text(json.dumps({
        "assignment_id": AID, "status": "diagnostic_offline_only_original_authority_pending", "cases": rows,
    }, indent=2) + "\n")
    print("built", len(rows), "exact bicycle red-signal diagnostic constructions")


if __name__ == "__main__":
    build()
