"""Regenerate the exact root delivery metadata from the selected case plan.

This does not alter the sealed per-case diagnostic constructions or their proofs.
"""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    construction = json.loads((ROOT / "construction.json").read_text(encoding="utf-8"))
    assert len(plan["cases"]) == 5
    assert {case["case_id"] for case in plan["cases"]} == set(config["supported_case_ids"])
    assert config["rate_hz"] == 20 and config["duration_s"] == 45
    plan["camera_plan"] = {
        "profile": "overview1080-capability",
        "duration_s": config["duration_s"],
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "bicycle route, alley, rack and pedestrian context",
             "interval": "complete original 45 s window at 20 Hz"},
            {"view": "approach", "subject": "bicycle approach speed, route and rack clearance",
             "interval": "complete original 45 s window at 20 Hz"},
            {"view": "reference_corner", "subject": "bicycle body, rack and nearby pedestrian",
             "interval": "complete original 45 s window at 20 Hz"},
            {"view": "driver_reference", "subject": "forward bicycle perspective and visibility conditions",
             "interval": "complete original 45 s window at 20 Hz"},
        ],
    }
    plan["source_observation_mapping"] = {}
    write(ROOT / "case-plan.json", plan)

    channels = construction["recording_description"]["channels"]
    if not any(row["name"] == "bicycle_subject_and_jurisdiction" for row in channels):
        channels.append({
            "name": "bicycle_subject_and_jurisdiction",
            "unit": "source-bound context",
            "method": "original actor classification and municipal map packet review",
            "time_window": "complete original 45 s window",
            "reference_frame": "reviewed municipal map and actor inventory",
            "uncertainty": "physical actor identity and City of Las Vegas location require original source review",
            "sampling_rate_hz": 20,
        })
    construction["measurement_plan"] = {
        "source": "original 20 Hz bicycle motion, time-joined conditions, actor and jurisdiction packets, and synchronized four-view video",
        "observations": plan["observations"],
        "comparisons": plan["comparisons"],
        "legal_reading": "record actual speed and contemporaneous conditions; leave reasonableness and prudence unresolved for review",
    }
    construction["static_checks"] = [
        "runner.py --check validates exact selected case, route, speed target and four-camera capture profile",
        "each exact case has current-runtime compatibility, saved-only, and independent delivery CPU proof",
        "source acquisition rejects missing or changed original packets and frame joins",
    ]
    construction["termination_rules"] = [
        "retain the original 45 s at 20 Hz or explicitly report incomplete physical capture",
        "reject missing original velocity, conditions, actor classification, jurisdiction or camera streams",
    ]
    construction["mechanisms"] = [
        "construct bicycle motion along authored alley beside the rack with exact selected speed target",
        "record route, rack, pedestrian and surface or visibility context for each selected case",
        "preserve declared fixed conditions across the planned comparisons",
    ]
    for entry in construction["files"]:
        source = ROOT / entry["path"]
        if source.is_file():
            entry["content"] = source.read_text(encoding="utf-8")
    write(ROOT / "construction.json", construction)


if __name__ == "__main__":
    main()
