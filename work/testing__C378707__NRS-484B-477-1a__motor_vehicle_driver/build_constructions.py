"""Materialize six exact primary and justified reverse-approach constructions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN_BYTES = (ROOT / "case-plan.json").read_bytes()
PLAN = json.loads(PLAN_BYTES)
CASES = json.loads((ROOT / "proposals/cases.json").read_text())
RECORDING = {row["case_id"]: row["recording_description"]
             for row in CASES["cases"] if row["target_type"] != "baseline"}
ASSIGNMENT = PLAN["assignment_id"]
FILES = ("runner.py", "native_acquisition.py", "alley_construction.py",
         "alley_activity.py", "audit_original_attempt.py", "audit_comparisons.py",
         "case-plan.json", "tests/test_bundle.py", "tests/test_alley_activity.py",
         "tests/test_alley_construction.py", "tests/test_native_acquisition.py")


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _cameras():
    return [
        {"name": "overview", "width": 1920, "height": 1080, "fov_deg": 75,
         "pose_strategy": "surveyed business alley and motor vehicle loading"},
        {"name": "approach", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "ego entry, original halt and departure"},
        {"name": "reference_corner", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "passenger, goods, door and surveyed loading zone"},
        {"name": "driver_reference", "width": 1280, "height": 720, "fov_deg": 75,
         "pose_strategy": "original driver presence and actor interaction"},
    ]


def build():
    all_ids = [row["case_id"] for row in PLAN["cases"]]
    for index, row in enumerate(PLAN["cases"]):
        variant = row["variant"]
        for candidate, direction in (("primary", 1), ("fallback1", -1)):
            base = ROOT / "cases" / variant
            if candidate != "primary":
                base /= candidate
            description = RECORDING[row["case_id"]]
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
                    "source-hashed reviewed business-district alley, frontage and jurisdiction",
                    "actual motor vehicle, passenger, goods and driver actor readback",
                    "900 original 20 Hz frames and four synchronized original cameras",
                    "effective reviewed local ordinance when selected"],
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
                                     "procedure": "alley_activity.py",
                                     "source_packets": ["reviewed_site", "actor_inventory",
                                                        "activity_history", "frame_map",
                                                        "four_original_camera_streams"],
                                     "legal_conclusion": "unreviewed"},
                "mechanisms": ["source-surveyed alley approach and vehicle halt",
                               "actual passenger, goods and driver actor control/readback",
                               "same-tick original activity and four-camera capture"],
                "static_checks": ["exact law, cell, actor, variant and plan hash",
                                  "reviewed business-district alley and local ordinance sources",
                                  "actual Native map and actor identity readback",
                                  "900 original frame and four-camera source joins"],
                "termination_rules": ["900 original Native ticks at 20 Hz",
                                      "fail closed on absent source or incomplete actor activity"],
            }
            _write(base / "construction.json", construction)
            if index == 0 and candidate == "primary":
                _write(ROOT / "config.json", config)
                _write(ROOT / "construction.json", construction)


if __name__ == "__main__":
    build()
