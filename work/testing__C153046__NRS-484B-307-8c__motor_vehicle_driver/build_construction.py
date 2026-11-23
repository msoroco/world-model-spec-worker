"""Build source-hashed, case-specific CPU construction proposals."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_case_plan import AID, KINDS, PAIRS
from recording_description import build as recording_description

ROOT = Path(__file__).resolve().parent
SOURCES = ["runner.py", "native_capture.py", "native_runner.py", "native_frame.py", "native_observation.py", "native_setup.py", "native_routes.py", "native_camera.py",
           "native_media.py", "saved_measurement.py",
           "comparison_audit.py",
           "red_left_turn_controller.py", "recording_description.py",
           "source_bound_scene.py", "build_case_plan.py", "case-plan.json",
           "tests/__init__.py", "tests/test_case_plan.py",
           "tests/test_red_left_turn_controller.py", "tests/test_source_bound_scene.py",
           "tests/test_native_runner.py", "tests/test_native_frame.py", "tests/test_runner_capture_closure.py",
           "tests/test_native_camera.py", "tests/test_native_media.py", "tests/test_native_setup.py", "tests/test_native_observation.py", "tests/test_native_capture.py", "tests/test_native_routes.py",
           "tests/test_saved_measurement.py", "tests/test_saved_finalizer.py", "tests/test_comparison_audit.py",
           "independent/__init__.py", "independent/delivery_audit.py",
           "tests/test_delivery_audit.py"]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    cases = []
    folder = ROOT / "constructions"
    folder.mkdir(exist_ok=True)
    for suffix, variables in KINDS.items():
        case_id = AID + "__" + suffix
        config = {"assignment_id": AID, "selected_case_id": case_id,
                  "law_id": "NRS-484B-307-8c", "cell_id": "C153046",
                  "actor": "motor_vehicle_driver", "rate_hz": 20, "duration_s": 30,
                  "cameras": [
                      {"name": name, "width": width, "height": height,
                       "pose_strategy": strategy, "fov_deg": 90}
                      for name, width, height, strategy in (
                          ("overview", 1920, 1080, "fixed intersection overhead"),
                          ("approach", 1280, 720, "fixed stop boundary and leftmost lane"),
                          ("reference_corner", 1280, 720, "fixed crosswalk and traffic conflict paths"),
                          ("driver_reference", 1280, 720, "ego mounted signal and receiving road view"))],
                  "capture_provenance": "original Native samples required",
                  "required_atoms": [], "source_packets": [],
                  "case": {"case_id": case_id, "draft_variables": variables,
                           "recording_description": recording_description()},
                  "physical_completion": {"criterion": "original stop, entry, yield, and exit histories",
                                          "status": "unverified"}}
        dispositions = json.loads((ROOT / "case-plan.json").read_text())["requirement_dispositions"]
        selected = [(index, row) for index, row in enumerate(dispositions)
                    if row["status"] == "selected_required" and
                    (not row.get("case_ids") or case_id in row["case_ids"])]
        contract = {
            "format": "worker-measurement-contract",
            "requirements": [{
                "disposition_index": index, "requirement": row["requirement"],
                "source": row["source"], "output_key": "red_left_turn_observation",
                "method": "measure", "value_type": "object", "kind": "measured",
                "inputs": ["site.json", "trace.jsonl"],
            } for index, row in selected],
            "negative": {"remove": ["site.json"],
                         "error_contains": "Missing required source: site.json"},
        }
        contract_path = folder / (suffix + "-measurement-contract.json")
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        files = [{"path": name, "content": (ROOT / name).read_text()} for name in SOURCES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        files.append({"path": "measurement-contract.json",
                      "content": json.dumps(contract, indent=2) + "\n"})
        construction = {"case_id": case_id, "cell_id": "C153046",
                        "law_id": "NRS-484B-307-8c", "actor": "motor_vehicle_driver",
                        "entrypoint": "runner.py", "files": files,
                        "recording_description": recording_description(),
                        "measurement_plan": {"entrypoint": "saved_measurement.py",
                                             "media_finalizer": "native_media.py",
                                             "sources": ["site.json", "trace.jsonl", "video_frames.jsonl",
                                                         "overview.mkv", "approach.mkv",
                                                         "reference_corner.mkv", "driver_reference.mkv"],
                                             "case_id": case_id},
                        "static_checks": ["exact site packet hashes and lane/turn geometry",
                                          "live OpenDRIVE and official signal actor match"],
                        "termination_rules": ["30 s maximum original frame capture",
                                              "stop on source or frame mismatch"],
                        "mechanisms": ["source-bound site geometry and live OpenDRIVE byte match",
                                       "source-cited Native participant spawn, world tick, signal, body and four-camera acquisition",
                                       "CARLA-lazy actor control application and text trace"],
                        "status": "partial: CPU protocol; reviewed site and physical proof pending"}
        path = folder / (suffix + ".json")
        path.write_text(json.dumps(construction, indent=2) + "\n")
        cases.append({"case_id": case_id, "kind": "delivery",
                      "construction": str(path.relative_to(ROOT)),
                      "construction_sha256": digest(path),
                      "measurement_contract": str(contract_path.relative_to(ROOT)),
                      "measurement_procedure": {"entrypoint": "saved_measurement.py"},
                      "delivery_acceptance_draft": {
                          "case_id": case_id, "sets": ["full-test"],
                          "checks": ["native_source", "all_participants", "time_join",
                                     "full_video_decode", "actual_pixels", "physical_completion"],
                          "script": "independent/delivery_audit.py",
                          "script_sha256": digest(ROOT / "independent" / "delivery_audit.py"),
                          "proof_status": "diagnostic_protocol_only_original_acceptance_pending"},
                      "candidate_risk": {"status": "unverified",
                                         "reason": "No reviewed site geometry yet; a concrete physical fallback trigger cannot be selected."},
                      "proof_status": "offline_pending_physical_and_compatibility"})
    comparisons = [{"comparison_id": name,
                    "case_ids": [AID + "__" + left, AID + "__" + right],
                    "deliberate_differences": [difference],
                    "independent_audit": "comparison_audit.py",
                    "proof_status": "synthetic_positive_negative_cpu_protocol_passed"}
                   for name, (left, right, difference) in PAIRS.items()]
    manifest = {"assignment_id": AID, "law_id": "NRS-484B-307-8c",
                "cell_id": "C153046", "actor": "motor_vehicle_driver", "cases": cases,
                "comparisons": comparisons,
                "status": "partial draft; no Native source, recording or delivery acceptance"}
    (ROOT / "execution-manifest.draft.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


if __name__ == "__main__":
    print("built", len(build()["cases"]), "exact construction proposals")
