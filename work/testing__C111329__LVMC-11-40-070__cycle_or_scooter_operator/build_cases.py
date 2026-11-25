"""Regenerate exact source-gated inline bundles from the frozen case plan.

Only stdlib sources are embedded. Run before binding proof hashes; never run this
script after proof binding without rechecking every selected construction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN_PATH = ROOT / "case-plan.json"
PLAN = json.loads(PLAN_PATH.read_text())
SOURCE_FILES = ("runner.py", "native_device.py", "native_officer.py", "native_route.py",
                "native_capture.py", "native_cameras.py", "saved_instruction.py")
TEST = '''import json
from pathlib import Path
import unittest
import runner

class BundleCheck(unittest.TestCase):
    def test_exact_identity(self):
        case = runner.check()
        self.assertEqual(case["case_id"], json.loads(Path("config.json").read_text())["selected_case_id"])

    def test_reviewed_source_is_required(self):
        with self.assertRaises(FileNotFoundError):
            runner.preflight_sources(runner.check(), Path("missing-original-site.json"), "0" * 64, None, None)
'''


def dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def make(case: dict) -> dict:
    suffix = case["case_id"].split("__")[-1]
    config = {
        "assignment_id": PLAN["assignment_id"], "law_id": PLAN["law_id"],
        "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
        "selected_case_id": case["case_id"],
        "supported_case_ids": [row["case_id"] for row in PLAN["cases"]],
        "case": {"case_id": case["case_id"]},
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
        "device_type": case["device_type"],
        "device_instruction": case["device_instruction"],
        "officer_direction": case["officer_direction"],
        "operator_motion": case["operator_motion"],
        "rate_hz": 20, "frame_count": 900, "duration_s": 45,
        "cameras": ["overview", "approach", "reference_corner", "driver_reference"],
        "required_atoms": [], "source_packets": [],
        "source_requirements": ["reviewed_native_site", "official_device_authority",
                                "vehicle_applicability", "original_bicycle_actor",
                                "reviewed_officer_authority_if_declared", "four_original_camera_streams"],
    }
    description = {
        "channels": [
            {"name": name, "unit": unit, "method": method,
             "sampling_rate_hz": 20, "time_window": "original 45-second instruction response",
             "reference_frame": "original Native frame and governed approach",
             "uncertainty": "physical realization and legal assessment remain unreviewed"}
            for name, unit, method in (
                ("bicycle_front_body_position", "m", "original Native bicycle pose and body extent"),
                ("bicycle_speed", "m/s", "original Native velocity readback"),
                ("device_instruction", "source state", "original governing device state readback"),
                ("police_officer_direction", "source state", "original officer gesture and recipient readback"),
            )],
        "context_inputs": [
            {"name": "reviewed_site", "unit": "source record", "method": "SHA-pinned original site and official applicability"},
            {"name": "reviewed_officer", "unit": "source record", "method": "SHA-pinned original officer authority when directed"},
        ],
        "limitations": ["Bicycle choice is one statutory actor alternative; no physical or legal outcome is asserted."],
    }
    files = [{"path": "config.json", "content": json.dumps(config, indent=2, sort_keys=True) + "\n"},
             {"path": "case-plan.json", "content": PLAN_PATH.read_text()},
             {"path": "tests/test_bundle.py", "content": TEST}]
    files.extend({"path": name, "source": str((ROOT / name).relative_to(Path.cwd())),
                  "content": (ROOT / name).read_text()} for name in SOURCE_FILES)
    construction = {"law_id": PLAN["law_id"], "cell_id": PLAN["cell_id"],
                    "actor": PLAN["actor"], "case_id": case["case_id"],
                    "entrypoint": "runner.py", "diagnostic_only": True,
                    "recording_description": description, "files": files}
    directory = ROOT / "cases" / suffix
    dump(directory / "construction.json", construction)
    return {"case_id": case["case_id"], "kind": "delivery",
            "construction": f"cases/{suffix}/construction.json",
            "construction_sha256": hashlib.sha256((directory / "construction.json").read_bytes()).hexdigest(),
            "candidate_risk": case["physical_risk"], "candidates": [],
            "physical_preparation_status": "unverified_original_capture_pending",
            "legal_necessity": "unresolved",
            "measurement_procedure": {"entrypoint": "saved_instruction.py"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}}


def main() -> None:
    entries = [make(case) for case in PLAN["cases"]]
    # A draft allows exact offline construction checks while remaining partial.
    dump(ROOT / "execution-manifest.draft.json", {
        "format": "worker-execution-manifest", "assignment_id": PLAN["assignment_id"],
        "status": "partial_cpu_preparation", "cases": entries})
    dump(ROOT / "config.json", json.loads(next(f["content"] for f in
         json.loads((ROOT / entries[0]["construction"]).read_text())["files"] if f["path"] == "config.json")))


if __name__ == "__main__":
    main()
