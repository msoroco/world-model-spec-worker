"""Build exact inline offline school-pass constructions from source files."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
RUNTIME = REPO / "runtime" / "SOURCE-MANIFEST.json"
CODE = (
    "runner.py", "school_timing.py", "school_pass.py", "school_scene_construction.py",
    "native_capture.py", "native_output_bridge.py", "saved_finalizer.py", "analysis.py",
    "case-plan.json", "tests/test_school_pass.py", "tests/test_school_timing.py",
    "tests/test_site_sources.py", "tests/test_native_capture.py",
    "tests/test_saved_finalizer.py", "tests/test_analysis.py",
)
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    all_ids = [row["case_id"] for row in plan["cases"]]
    cameras = [
        {"name": view, "width": 1920 if view == "overview" else 1280,
         "height": 1080 if view == "overview" else 720,
         "fov_deg": 80,
         "pose_strategy": "source-reviewed ego/target passing lane, designated zone extent and school beacon/sign"}
        for view in VIEWS
    ]
    description = {
        "channels": [
            {"name": name, "unit": "structured", "method": "source-sealed original Native readback",
             "reference_frame": "reviewed school-zone map", "sampling_rate_hz": 20,
             "time_window": "all 900 original frames",
             "uncertainty": "physical passing and legal exception application await original capture review"}
            for name in ("same_direction_pass", "designated_zone_extent", "beacon_sign_readback",
                         "school_schedule_and_clock", "four_camera_pixels")
        ],
        "context_inputs": [{"name": "reviewed_original_school_sources", "unit": "source",
                            "method": "SHA-256 sealed site, calendar, beacon, sign and original map survey"}],
        "limitations": ["Engineering passing and clock measurements do not decide legal compliance.",
                        "CPU source fixtures do not prove physical passing, lamp pixels or visibility."],
    }
    entries = []
    for row in plan["cases"]:
        case_id = row["case_id"]
        name = case_id[len(ASSIGNMENT) + 2:]
        config = {
            "assignment_id": ASSIGNMENT, "cell_id": "C261489", "law_id": "NRS-484B-363-4",
            "actor": "motor_vehicle_driver", "selected_case_id": case_id,
            "supported_case_ids": all_ids, "plan_sha256": sha(HERE / "case-plan.json"),
            "rate_hz": 20, "duration_s": 45, "cameras": cameras,
            "required_atoms": [], "source_packets": [],
            "case": {"case_id": case_id, "recording_description": description},
        }
        location = HERE / "cases" / name
        write(location / "config.json", config)
        files = [{"path": "config.json", "content": (location / "config.json").read_text(),
                  "source": str((location / "config.json").relative_to(REPO))}]
        files += [{"path": relative, "content": (HERE / relative).read_text(),
                   "source": str((HERE / relative).relative_to(REPO))} for relative in CODE]
        construction = {
            "cell_id": "C261489", "actor": "motor_vehicle_driver", "law_id": "NRS-484B-363-4",
            "case_id": case_id, "status": "source_gated_incomplete", "entrypoint": "runner.py",
            "files": files,
            "mechanisms": ["reviewed same-direction two-lane passing route",
                           "source-bound school-zone boundary and school-property adjacency",
                           "independent school calendar, local clock, operation/class schedule",
                           "synchronized sign and alternating-yellow-lamp readback",
                           "four original RGB camera streams"],
            "measurement_plan": {"case_id": case_id, "procedure": "school_pass.py:measure_original",
                                 "source_packets": ["reviewed_school_site", "original_context",
                                                    "original_trace", "original_camera_manifest"],
                                 "legal_judgment": "unresolved"},
            "recording_description": description,
            "static_checks": ["exact assignment and plan SHA", "all original site source hashes",
                              "both same-direction lane route IDs and 900-frame 20 Hz four-camera plan"],
            "termination_rules": ["stop on Native source or frame mismatch",
                                  "destroy owned actors and restore previous world settings"],
        }
        write(location / "construction.json", construction)
        entries.append({
            "case_id": case_id, "kind": "delivery",
            "construction": str((location / "construction.json").relative_to(HERE)),
            "construction_sha256": sha(location / "construction.json"),
            "candidate_risk": {"status": "physical", "reason": "Lane-change pass and beacon/zone camera framing may fail on the first surveyed route."},
            "candidates": [],
        })
    write(HERE / "config.json", json.loads((HERE / "cases" / plan["cases"][0]["case_id"].split("__")[-1] / "config.json").read_text()))
    write(HERE / "construction.json", json.loads((HERE / entries[0]["construction"]).read_text()))
    write(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": ASSIGNMENT,
        "runtime_manifest_sha256": sha(RUNTIME), "status": "partial_cpu_construction",
        "cases": entries,
    })
    print(json.dumps({"constructions": len(entries), "runtime_manifest_sha256": sha(RUNTIME)}))


if __name__ == "__main__":
    main()
