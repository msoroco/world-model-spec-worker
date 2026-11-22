"""Independent realized red-X entry and driving pair checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from analysis import build_report


ASSIGNMENT = "testing__C147332__NRS-484B-307-12b__bus_driver"
PAIRS = {"red_x_lateral_entry": ("adjacent_travel", "lateral_entry", "red_x_entry_frames"),
         "red_x_in_lane_driving": ("red_lane_stand", "red_lane_drive", "red_x_driving_frames")}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_pair(comparison_id, baseline, changed):
    if comparison_id not in PAIRS:
        raise ValueError("unknown exact red-X comparison")
    expected_left, expected_right, metric = PAIRS[comparison_id]
    baseline, changed = Path(baseline), Path(changed)
    scenes = [json.loads((folder / "scene.json").read_text()) for folder in (baseline, changed)]
    for scene, suffix in zip(scenes, (expected_left, expected_right)):
        if scene.get("case_id") != ASSIGNMENT + "__" + suffix:
            raise ValueError("wrong exact comparison case")
    reports = [build_report(folder) for folder in (baseline, changed)]
    if reports[0]["site_review"] != reports[1]["site_review"]:
        raise ValueError("reviewed highway or official red-X device changed")
    for folder, scene in zip((baseline, changed), scenes):
        acquisition = json.loads((folder / "acquisition.json").read_text())
        map_hash = _sha(folder / "road.xodr")
        source = acquisition.get("road.xodr")
        recorded = source.get("sha256") if isinstance(source, dict) else source
        if map_hash != recorded or map_hash != scene.get("map_source_sha256"):
            raise ValueError("original map source changed within exact case")
    if _sha(baseline / "road.xodr") != _sha(changed / "road.xodr"):
        raise ValueError("comparison road differs")
    fixed_fields = ("law_id", "cell_id", "actor", "layout", "control", "bus_blueprint_id",
                    "signal", "capture_plan")
    if any(scenes[0].get(key) != scenes[1].get(key) for key in fixed_fields):
        raise ValueError("comparison fixed condition changed")
    first = reports[0]["measurements"]["red_x_bus_lane"]
    second = reports[1]["measurements"]["red_x_bus_lane"]
    if first[metric] or not second[metric]:
        raise ValueError("realized red-X comparison contrast absent")
    return {"comparison_id": comparison_id, "baseline_case_id": scenes[0]["case_id"],
            "changed_case_id": scenes[1]["case_id"],
            "fixed_original_road_sha256": _sha(baseline / "road.xodr"),
            "reviewed_site": reports[0]["site_review"],
            "realized_baseline_frames": first[metric], "realized_changed_frames": second[metric],
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}
