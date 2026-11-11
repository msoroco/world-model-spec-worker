"""Independent source audit of the opposite-direction left-turn exception trio."""
import hashlib
import json
import math
from pathlib import Path

from crossing_precedence import analyze

MODES = ("straight", "intends_left", "makes_left")
FIXED = ("native_map_id", "intersection_id", "ego_highway_id",
         "other_highway_id", "ego_road_id", "other_road_id",
         "intersection_polygon_xy_m", "crossing_geometry_source",
         "all_entrances_source", "official_device_inventory_source",
         "median_spacing_source", "same_statutory_crossing",
         "official_device_controls_crossing", "camera_plan_sha256",
         "approach_geometry_source")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def _heading(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("Original finite heading required")
    return float(value)


def _turn_change(headings):
    return sum((end - start + 180) % 360 - 180
               for start, end in zip(headings, headings[1:]))


def audit_source(root: Path, mode: str, expected_frames: int) -> dict:
    if mode not in MODES or type(expected_frames) is not int or expected_frames < 3:
        raise ValueError("Exact exception mode and full frame count required")
    root = Path(root)
    report = analyze(root, allow_exceptions=True)
    context = json.loads((root / "junction_context.json").read_text())
    for key in ("camera_plan_sha256", "approach_geometry_source",
                "opposite_approach_source"):
        if not context.get(key):
            raise ValueError("Missing sourced exception context: " + key)
    rows = _rows(root / "crossing_history.jsonl")
    if len(rows) != expected_frames:
        raise ValueError("Full exception history duration required")
    plan_path = root / "route_intent.json"
    if not plan_path.is_file():
        raise ValueError("Missing original authored route intent")
    plan = json.loads(plan_path.read_text())
    source = plan.get("route_plan_source")
    if not isinstance(source, dict) or set(source) != {"path", "sha256"}:
        raise ValueError("Hashed authored route-plan source required")
    source_path = root / source["path"]
    if not source_path.is_file() or _sha(source_path) != source["sha256"]:
        raise ValueError("Authored route-plan source changed")
    if plan.get("ego_turn_intent") != "straight" or plan.get("other_turn_intent") not in ("straight", "left"):
        raise ValueError("Explicit ego and other route intentions required")
    ids = {role: plan.get(role + "_actor_id") for role in ("ego", "other")}
    if any(type(value) is not int for value in ids.values()) or ids["ego"] == ids["other"]:
        raise ValueError("Distinct route-intent actor identities required")
    headings = {role: [] for role in ids}
    for row in rows:
        for role in ids:
            actor = row.get(role, {})
            if actor.get("actor_id") != ids[role]:
                raise ValueError("Original actor differs from authored route intent")
            headings[role].append(_heading(actor.get("heading_deg")))
    difference = abs((_heading(headings["other"][0]) - _heading(headings["ego"][0]) + 180) % 360 - 180)
    if difference < 160:
        raise ValueError("Original approaches are not opposite directions")
    if context.get("opposite_approach") is not True:
        raise ValueError("Opposite approach source conclusion missing")
    change = _turn_change(headings["other"])
    intent_left = plan["other_turn_intent"] == "left"
    if mode == "straight" and (intent_left or abs(change) > 15):
        raise ValueError("Straight case has left intent or observed turn")
    if mode == "intends_left" and (not intent_left or abs(change) > 15):
        raise ValueError("Intent-only case must retain left intent without observed turn")
    if mode == "makes_left" and (not intent_left or not 45 <= change <= 135):
        raise ValueError("Making-left case lacks original observed left rotation")
    exception = intent_left or 45 <= change <= 135
    if context.get("opposite_approach_with_left_turn") is not exception:
        raise ValueError("Declared left-turn exception differs from original sources")
    return {"mode": mode, "frames": expected_frames,
            "sources": {**report["sources"], "route_intent.json": _sha(plan_path),
                        source["path"]: source["sha256"]},
            "first_body_entry": report["first_body_entry"],
            "other_heading_change_deg": change,
            "other_left_intent_authored": intent_left,
            "opposite_initial_heading_difference_deg": difference,
            "declared_exception_matches_sources": True,
            "subsection_1_exception_active": exception,
            "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}


def audit_trio(roots: dict, expected_frames: int) -> dict:
    if not isinstance(roots, dict) or set(roots) != set(MODES):
        raise ValueError("All three exact opposite-turn sources required")
    reports = {mode: audit_source(roots[mode], mode, expected_frames) for mode in MODES}
    contexts = {mode: json.loads((Path(roots[mode]) / "junction_context.json").read_text())
                for mode in MODES}
    baseline = contexts["straight"]
    for mode in MODES[1:]:
        for key in FIXED:
            if contexts[mode].get(key) != baseline.get(key):
                raise ValueError("Fixed opposite-turn condition changed: " + key)
    source_rows = {mode: _rows(Path(roots[mode]) / "crossing_history.jsonl") for mode in MODES}
    for index in range(expected_frames):
        frame_time = (source_rows["straight"][index]["frame"],
                      source_rows["straight"][index]["time_s"])
        if any((source_rows[mode][index]["frame"], source_rows[mode][index]["time_s"]) != frame_time
               for mode in MODES[1:]):
            raise ValueError("Fixed opposite-turn frame or time changed")
    if reports["straight"]["subsection_1_exception_active"] or not all(
            reports[mode]["subsection_1_exception_active"] for mode in MODES[1:]):
        raise ValueError("Opposite-turn exception contrast missing")
    return {"format": "worker-opposite-left-turn-exception-comparison",
            "comparison_id": "opposite_left_turn_exception",
            "expected_frames": expected_frames,
            "cases": reports,
            "software_comparison_passed": True,
            "physical_acceptance_claimed": False,
            "legal_conclusion": "unresolved"}
