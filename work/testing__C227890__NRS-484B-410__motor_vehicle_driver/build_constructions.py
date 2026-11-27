"""Materialize exact primary and justified alternate-bay parked departures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_semantic import recording_description

ROOT = Path(__file__).resolve().parent
PLAN_BYTES = (ROOT / "case-plan.json").read_bytes()
PLAN = json.loads(PLAN_BYTES)
ASSIGNMENT = PLAN["assignment_id"]
FILES = ("runner.py", "native_acquisition.py", "finalize_native.py",
         "parked_construction.py", "parked_activity.py", "analysis.py",
         "audit_original_attempt.py", "audit_comparisons.py", "case-plan.json",
         "tests/test_native_acquisition.py", "tests/test_parked_construction.py",
         "tests/test_parked_activity.py")


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def _cameras():
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 75,
         "pose_strategy": "reviewed public highway and parked departure corridor"},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "other vehicle approach from rear or opposing route"},
        {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "legal parking bay, curb and parked starting pose"},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "responsible driver, original controls and departure"},
    ]


def build():
    all_ids = [row["case_id"] for row in PLAN["cases"]]
    description = recording_description()
    for index, row in enumerate(PLAN["cases"]):
        variant = row["variant"]
        for candidate, direction in (("primary", 1), ("fallback1", -1)):
            base = ROOT / "cases" / variant
            if candidate != "primary":
                base /= candidate
            config = {
                "assignment_id": ASSIGNMENT, "law_id": PLAN["law_id"],
                "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
                "selected_case_id": row["case_id"], "variant": variant,
                "supported_case_ids": all_ids,
                "plan_sha256": hashlib.sha256(PLAN_BYTES).hexdigest(),
                "approach_direction": direction, "duration_s": 45,
                "rate_hz": 20, "frame_count": 900, "cameras": _cameras(),
                "diagnostic_only": True, "required_atoms": [], "source_packets": [],
                "case": {"case_id": row["case_id"], "recording_description": description},
                "recording_description": description,
                "source_requirements": [
                    "source-hashed public highway dedication, vehicular use and boundaries",
                    "source-hashed location and time specific parking permission",
                    "actual ordinary vehicle, responsible driver and other vehicle readback",
                    "900 original 20 Hz frames and four synchronized original cameras"],
            }
            _write(base / "config.json", config)
            file_rows = [{"path": name, "source": "work/" + ASSIGNMENT + "/" + name,
                          "content": (ROOT / name).read_text()} for name in FILES]
            file_rows.append({"path": "config.json",
                              "source": "work/" + ASSIGNMENT + "/" + str((base / "config.json").relative_to(ROOT)),
                              "content": (base / "config.json").read_text()})
            construction = {
                "case_id": row["case_id"], "law_id": PLAN["law_id"],
                "cell_id": PLAN["cell_id"], "actor": PLAN["actor"],
                "entrypoint": "runner.py", "files": file_rows,
                "recording_description": description,
                "measurement_plan": {"case_id": row["case_id"],
                                     "procedure": "parked_activity.py",
                                     "source_packets": ["reviewed_site", "actor_inventory",
                                                        "activity_history", "frame_map",
                                                        "four_original_camera_streams"],
                                     "legal_conclusion": "unreviewed"},
                "mechanisms": ["source-surveyed permitted parked position and two approach routes",
                               "actual driver and other vehicle original control/readback",
                               "same-tick original activity and four-camera capture"],
                "static_checks": ["exact law, cell, actor, variant and plan hash",
                                  "reviewed public highway, parking rule and approach sources",
                                  "actual Native map and actor identity readback",
                                  "900 original frames and four-camera source joins"],
                "termination_rules": ["900 original Native ticks at 20 Hz",
                                      "fail closed on absent source, motion or incomplete camera activity"],
            }
            _write(base / "construction.json", construction)
            if index == 0 and candidate == "primary":
                _write(ROOT / "config.json", config)
                _write(ROOT / "construction.json", construction)


if __name__ == "__main__":
    build()
