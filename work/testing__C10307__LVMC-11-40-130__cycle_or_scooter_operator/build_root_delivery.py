"""Regenerate the exact root delivery metadata from the selected case plan.

This does not alter the sealed per-case diagnostic constructions or their proofs.
"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
    for observation in plan["observations"]:
        if observation["name"] == "bicycle_subject_and_jurisdiction":
            observation["mandatory"] = False
            observation["capture_via"] = "reviewed source packets in recording_description.context_inputs"
    write(ROOT / "case-plan.json", plan)

    channels = construction["recording_description"]["channels"]
    channels[:] = [row for row in channels
                   if row["name"] != "bicycle_subject_and_jurisdiction"]
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
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["cases"]:
        source = ROOT / entry["construction"]
        if source != ROOT / "construction.json":
            exact_construction = json.loads(source.read_text(encoding="utf-8"))
            exact_construction["recording_description"] = construction["recording_description"]
            for file_entry in exact_construction["files"]:
                original = (REPO / file_entry["source"] if file_entry.get("source")
                            else source.parent / file_entry["path"])
                if original.is_file():
                    file_entry["content"] = original.read_text(encoding="utf-8")
            write(source, exact_construction)
        entry["construction_sha256"] = sha(source)
        entry["offline"]["construction_sha256"] = entry["construction_sha256"]
        entry["acquisition"].pop("bicycle_subject_and_jurisdiction", None)
    for proposal_name in ("cases-stage.json", "cases.json"):
        proposal_path = ROOT / "proposals" / proposal_name
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        for selected in proposal["cases"]:
            if selected["target_type"] != "baseline":
                selected["recording_description"] = construction["recording_description"]
        for sweep in proposal["sweep_specs"]:
            sweep["recording_description"] = construction["recording_description"]
        write(proposal_path, proposal)
    semantic_path = ROOT / "proposals/semantic-index.json"
    semantic = json.loads(semantic_path.read_text(encoding="utf-8"))
    semantic["stages"]["cases"]["sha256"] = sha(ROOT / "proposals/cases-stage.json")
    write(semantic_path, semantic)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
