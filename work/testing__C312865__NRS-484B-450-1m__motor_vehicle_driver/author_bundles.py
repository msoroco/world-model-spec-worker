"""Materialize exact source-bound tunnel constructions for the current runtime."""
from __future__ import annotations

import json
from pathlib import Path

from tunnel import CASES

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
LAW = "NRS-484B-450-1m"
FILES = ("runner.py", "native_tunnel.py", "site_review.py", "tunnel.py",
         "analysis.py", "case-plan.json", "tests/test_tunnel.py")
CAMERAS = [
    {"name": name, "width": width, "height": height,
     "pose_strategy": strategy, "fov_deg": 90}
    for name, width, height, strategy in (
        ("overview", 1920, 1080, "fixed both portals, highway and vehicles"),
        ("approach", 1280, 720, "fixed ego and entry portal"),
        ("tunnel_reference", 1280, 720, "fixed full ego body and tunnel interior"),
        ("driver_reference", 1280, 720, "ego mounted other-vehicle context"))]
CHANNELS = ("site_source", "tunnel_boundary", "ego_body_footprint",
            "ego_motion_history", "other_vehicle_motion_history",
            "other_vehicle_purpose", "halt_activity_history",
            "exception_context", "camera_frame_map")
CONTEXT = ("highway_status", "driver_identity", "motor_vehicle_class",
           "tunnel_portals", "traffic_conflict_necessity", "law_compliance",
           "police_direction", "official_device_direction")


def recording():
    return {
        "channels": [{
            "name": name, "unit": "structured record", "sampling_rate_hz": 20,
            "method": "Original Native frame acquisition and saved-only extraction",
            "time_window": "tunnel approach through terminal halt",
            "reference_frame": "original CARLA world frame and timestamp",
            "uncertainty": "20 Hz sampling, tunnel source geometry and actor bounding box",
        } for name in CHANNELS],
        "context_inputs": [{
            "name": name, "unit": "reviewed source packet",
            "method": "Reviewed original highway, tunnel, portal and authority source binding",
        } for name in CONTEXT],
        "limitations": [
            "Geometry alone does not establish legally qualifying highway status.",
            "A requested stop, stand or park activity and exception context require original independent review.",
            "Physical pixels and legal applicability require independent original review.",
        ],
    }


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    all_ids = [AID + "__" + case.case_id for case in CASES]
    description = recording()
    for index, case in enumerate(CASES):
        case_id = all_ids[index]
        config = {
            "assignment_id": AID, "selected_case_id": case_id,
            "supported_case_ids": all_ids, "law_id": LAW,
            "cell_id": "C312865", "actor": "motor_vehicle_driver",
            "rate_hz": 20, "duration_s": 45,
            "engineering_throttle": .25, "engineering_braking_factor": 5.0,
            "required_atoms": [], "source_packets": [], "cameras": CAMERAS,
            "physical_completion": {
                "criterion": "travel_progress", "motion_source": "trace.jsonl",
                "position_key": "position_m", "minimum_progress_m": 4,
                "minimum_samples": 2, "engineering_tolerances_not_legal": True,
            },
            "case": {"case_id": case_id, "endpoint": case.endpoint,
                     "halt_activity": case.activity,
                     "exception_probe": case.exception_probe,
                     "recording_description": description},
        }
        files = [{"path": name,
                  "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                  "content": (ROOT / name).read_text(encoding="utf-8")}
                 for name in FILES]
        files.append({"path": "config.json", "content": json.dumps(config, indent=2) + "\n"})
        construction = {
            "law_id": LAW, "cell_id": "C312865", "actor": "motor_vehicle_driver",
            "case_id": case_id, "entrypoint": "runner.py", "files": files,
            "measurement_plan": [{
                "name": "tunnel_body_halt_and_exception_context", "method": "analysis.analyze",
                "sources": ["tunnel-site.json", "tunnel-history.jsonl",
                            "video_frames.jsonl", "trace.jsonl"],
            }],
            "recording_description": description,
            "static_checks": [
                "exact case and reviewed original highway, tunnel, portal and map hashes",
                "distinct motor vehicles, full-body tunnel boundary and outside target",
                "ego halt, other vehicle motion/purpose and original exception authority",
            ],
            "termination_rules": [
                "45 seconds at 20 Hz with approach and terminal stop, stand or park",
                "failed frame join, source readback, cleanup or restoration rejects capture",
            ],
            "mechanisms": [
                "reviewed highway, tunnel, portal and map source gate",
                "source-bound ego and other motor vehicles",
                "ego halt controller with other-vehicle context",
                "four synchronized cameras and original frame map",
                "saved-only source-bound finalizer",
            ],
        }
        folder = ROOT if index == 0 else ROOT / "cases" / case.case_id
        write(folder / "config.json", config)
        write(folder / "construction.json", construction)


if __name__ == "__main__":
    main()
