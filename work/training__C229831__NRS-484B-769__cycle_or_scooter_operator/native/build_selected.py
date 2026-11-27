"""Write three exact source-bound primary drafts and one justified rig fallback.

This builder does not claim package readiness; receipts are added only after
their corresponding CPU proof commands have passed.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
AID = FOLDER.name
SOURCE_PATHS = (
    "runner.py", "finalize.py", "native/runner.py", "native/road.py",
    "native/route_control.py", "native/rider_arm.py", "native/source_rows.py",
    "native/measure_hand_signal.py", "native/measure_general_signal.py",
    "native/finalize_sources.py", "native/audit_arm_cases.py",
)
NAMES = ("overview", "approach", "reference_corner", "driver_reference")
ATOMS = ("sig.hand_signal", "ru.subject", "ru.bicycle", "ru.electric_bicycle",
         "ru.electric_scooter", "st.roadway", "drv.turning")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def recording_description():
    return {
        "channels": [{"name": name, "unit": "structured",
                      "method": "600 original Native rider bones, full bicycle body and synchronized camera source join",
                      "sampling_rate_hz": 20, "time_window": "30 s / 600 original frames",
                      "reference_frame": "original Native road map and frame",
                      "uncertainty": "Actual mount, pixel visibility and legal meaning need independent local review"}
                     for name in ATOMS],
        "context_inputs": [{"name": "rider_arm_roadway_context", "unit": "structured",
                            "method": "Original Native map, bicycle and rider identity readback"}],
        "limitations": ["Pose margins are engineering diagnostics, not legal thresholds.",
                        "Synthetic fixtures cannot prove physical arm visibility or signaling."],
    }


def build(case_id, candidate):
    description = recording_description()
    config = {
        "assignment_id": AID, "case_id": case_id, "selected_case_id": case_id,
        "supported_case_ids": [AID + "__probe_" + key for key in "abc"],
        "candidate_id": candidate, "cell_id": "C229831", "law_id": "NRS-484B-769",
        "actor": "cycle_or_scooter_operator", "rate_hz": 20, "duration_s": 30,
        "frames": 600,
        "cameras": [{"name": name, "width": 1920 if name == "overview" else 1280,
                     "height": 1080 if name == "overview" else 720,
                     "pose_strategy": "fixed original road and intersection capture",
                     "fov_deg": 90} for name in NAMES],
        "recording_description": description, "required_atoms": [], "source_packets": [],
        "walker_blueprint": "walker.pedestrian.0002" if candidate == "fallback1" else "walker.pedestrian.0001",
        "physical_completion": {"criterion": "turn", "motion_source": "trace.jsonl",
                                "position_key": "position_m", "heading_key": "heading_deg",
                                "turn_degrees": 90, "turn_sign": -1,
                                "turn_tolerance_deg": 30,
                                "minimum_progress_m": 8,
                                "engineering_tolerances_not_legal": True},
        "physical_acceptance_claimed": False,
        "case": {"case_id": case_id, "recording_description": description},
    }
    files = []
    for relative in SOURCE_PATHS:
        path = FOLDER / relative
        files.append({"path": relative,
                      "source": path.relative_to(REPO).as_posix(),
                      "content": path.read_text()})
    test = FOLDER / "native/selected_test.py"
    files.append({"path": "tests/test_selected.py",
                  "source": test.relative_to(REPO).as_posix(),
                  "content": test.read_text()})
    files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
    construction = {
        "case_id": case_id, "cell_id": "C229831", "law_id": "NRS-484B-769",
        "actor": "cycle_or_scooter_operator", "entrypoint": "runner.py",
        "files": files, "recording_description": description,
        "measurement_plan": "Source-sealed right horizontal, no signal and referenced left upward arm geometry on a connected roadway right turn; no legal verdict.",
        "static_checks": ["three-road connected OpenDRIVE and four-view profile",
                          "600 original rider, camera, motion, trace and event frame joins"],
        "termination_rules": ["600 original frames at 20 Hz", "reject source gaps and restore owned world"],
        "mechanisms": ["Native bicycle route controller", "distinct articulated rider bone control and readback",
                       "original four-view lossless capture", "saved sealed-source independent arm audit"],
        "status": "selected_cpu_construction_draft",
    }
    out = FOLDER / "native/selected-drafts" / case_id.rsplit("__", 1)[-1] / candidate / "construction.json"
    write(out, construction)
    return out, construction, config


def main():
    entries = []
    for key in "abc":
        case = AID + "__probe_" + key
        primary_path, primary, config = build(case, "primary")
        fallback_path, fallback, _ = build(case, "fallback1")
        entry = {
            "case_id": case, "kind": "delivery", "id": "primary",
            "construction": primary_path.relative_to(FOLDER).as_posix(),
            "construction_sha256": sha(primary_path),
            "candidate_risk": {"status": "physical",
                "reason": "Walker skeleton or arm articulation may be unavailable or fail to show the requested pose."},
            "candidates": [{"id": "fallback1",
                "construction": fallback_path.relative_to(FOLDER).as_posix(),
                "construction_sha256": sha(fallback_path),
                "trigger": {"source": "native-capture-report.json",
                    "metric": "rider_blueprint_and_arm_readback",
                    "failure_condition": "selected walker blueprint unavailable or original arm readback absent"},
                "changed_knobs": ["walker.pedestrian.0001 to walker.pedestrian.0002"]}],
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "worker-c229831-saved-analysis-v1"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
        }
        entries.append(entry)
        if key == "a":
            write(FOLDER / "config.json", config)
            write(FOLDER / "construction.json", primary)
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "status": "selected_cpu_construction_partial",
                "cases": entries}
    write(FOLDER / "execution-manifest.json", manifest)
    print(json.dumps({"exact_cases": len(entries), "primary_drafts": len(entries),
                      "justified_fallback_drafts": len(entries),
                      "package_ready": False}))


if __name__ == "__main__":
    main()
