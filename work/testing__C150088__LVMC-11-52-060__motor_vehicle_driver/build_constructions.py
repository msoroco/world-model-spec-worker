"""Rebuild immutable exact-case source bundles from owned implementation files."""

from __future__ import annotations

import json
from pathlib import Path

from projection_construction import CASES
from projection_measurement import ASSIGNMENT

ROOT = Path(__file__).resolve().parent
MODULES = ("runner.py", "analysis.py", "projection_measurement.py",
           "projection_construction.py", "projection_sources.py", "projection_capture.py",
           "physical_completion.py")
TESTS = tuple("tests/" + p.name for p in sorted((ROOT / "tests").glob("test*.py")))
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def description():
    channels = []
    for name, unit, method in (
        ("maximum_perpendicular_projection", "metres", "complete original vehicle, load and trailer outline vertices measured normal to reviewed curb"),
        ("controlling_physical_part", "original category", "outermost actual vehicle, load or attached trailer part"),
        ("curb_street_side_geometry", "original coordinates", "reviewed curb line and independently confirmed street side"),
        ("parked_assembly_stability", "metres", "900-frame maximum minus minimum original projection"),
        ("camera_frame_identity", "Native frame ID", "four synchronized original cameras"),
    ):
        channels.append({"name": name, "unit": unit, "method": method,
                         "sampling_rate_hz": 20, "time_window": "all 900 original frames",
                         "reference_frame": "original Native map and curb survey",
                         "uncertainty": "engineering target and synthetic fixture do not establish legal equality or physical visibility"})
    return {"channels": channels, "context_inputs": [
        {"name": "reviewed_original_opendrive_and_curb_survey", "unit": "source hashes",
         "method": "local source packet plus Native map and curb readback"},
        {"name": "vehicle_load_trailer_attachment", "unit": "source actor IDs",
         "method": "original Native attachment and hitch readback"}],
        "limitations": ["The statutory boundary is exactly fifteen feet (4.572 m); the 0.08 m construction tolerance is engineering only.",
                        "Physical pixel visibility and legal interpretation require independent local review."]}


def write():
    source_paths = MODULES + TESTS
    desc = description()
    output = []
    for index, case in enumerate(CASES):
      for candidate in ("primary", "fallback1"):
        base = ROOT if index == 0 and candidate == "primary" else ROOT / "cases" / case.suffix
        base.mkdir(parents=True, exist_ok=True)
        config = {"assignment_id": ASSIGNMENT, "law_id": "LVMC-11-52-060",
                  "cell_id": "C150088", "actor": "motor_vehicle_driver",
                  "selected_case_id": case.case_id,
                  "supported_case_ids": [item.case_id for item in CASES],
                  "rate_hz": 20, "duration_s": 45, "frame_count": 900,
                  "required_atoms": [], "source_packets": [],
                  "requested_projection_m": case.projection_m,
                  "controlling_part": case.controlling_part,
                  "candidate_id": candidate,
                  "cameras": [{"name": name, "width": width, "height": height,
                               "pose_strategy": "reviewed original curb/assembly survey",
                               "fov_deg": 90} for name, width, height in CAMERAS],
                  "case": {"case_id": case.case_id, "recording_description": desc}}
        config_name = "config.json" if candidate == "primary" else "fallback1-config.json"
        (base / config_name).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        files = [{"path": name, "source": str((ROOT / name).relative_to(ROOT.parents[1])),
                  "content": (ROOT / name).read_text(encoding="utf-8")} for name in source_paths]
        files.append({"path": "config.json", "content": (base / config_name).read_text(encoding="utf-8")})
        construction = {"law_id": "LVMC-11-52-060", "cell_id": "C150088",
                        "actor": "motor_vehicle_driver", "case_id": case.case_id,
                        "candidate_id": candidate,
                        "entrypoint": "runner.py", "diagnostic_only": True,
                        "recording_description": desc, "files": files,
                        "measurement_plan": "900 original complete part outlines with signed perpendicular curb projection",
                        "static_checks": ["reviewed source hashes", "loaded Native map and curb readback",
                                          "parking brake and attached part readback", "four camera frame joins"],
                        "termination_rules": ["900 synchronized Native ticks", "verified world restoration"],
                        "mechanisms": ["source-gated parked physical assembly", "sealed original Native capture"]}
        construction_name = "construction.json" if candidate == "primary" else "fallback1-construction.json"
        (base / construction_name).write_text(json.dumps(construction, indent=2) + "\n", encoding="utf-8")
        output.append((case.case_id, candidate, base / construction_name))
    return output


if __name__ == "__main__":
    for case_id, candidate, path in write():
        print(case_id, candidate, path)
