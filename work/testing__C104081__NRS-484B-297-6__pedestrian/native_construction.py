"""Lazy Native construction boundary for the five authored sidewalk bypass cases.

The caller supplies a CARLA-capable adapter after loading a source-bound site
survey. This module imports no simulator and does not claim a map was surveyed.
"""

import hashlib
import json
from pathlib import Path

from geometry import audit_design, construct


REQUIRED_SURFACES = ("sidewalk", "intervening_area", "designated_bicycle_lane",
                     "immediately_adjacent_highway")


def load_site_survey(path: Path, expected_sha256: str, expected_cell: str = "C104081") -> dict:
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("site survey digest mismatch")
    survey = json.loads(raw)
    if survey.get("source_kind") != "original_native_map_survey":
        raise ValueError("site survey must be source-bound original Native data")
    if survey.get("cell_id") != expected_cell or not survey.get("map_id"):
        raise ValueError("site survey cell/map identity mismatch")
    if survey.get("layout") != "hill_crest":
        raise ValueError("site survey does not retain hill-crest layout")
    if not all(survey.get("surfaces", {}).get(name, {}).get("surveyed") is True
               for name in REQUIRED_SURFACES):
        raise ValueError("site survey lacks a required observed surface")
    transform = survey.get("local_to_world")
    if not isinstance(transform, dict) or not all(
            isinstance(transform.get(key), (int, float)) for key in ("x", "y", "yaw_degrees")):
        raise ValueError("site survey lacks local-to-world transform")
    return survey


def _case_parameters(plan: dict, case_id: str) -> dict:
    if plan.get("cell_id") != "C104081" or plan.get("actor") != "pedestrian":
        raise ValueError("wrong assignment plan for pedestrian construction")
    matches = [item for item in plan["cases"] if item["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("case is not exact or unique in plan")
    return matches[0]["construction_parameters"]


def construct_native(plan: dict, case_id: str, survey_path: Path,
                     survey_sha256: str, adapter) -> dict:
    """Create and read back route resources through a supplied Native adapter.

    Adapter operations are intentionally explicit so a future CARLA binding must
    implement actual world calls. On an error, only owned created handles are
    destroyed; the caller remains responsible for world snapshot/restore.
    """
    survey = load_site_survey(survey_path, survey_sha256, plan.get("cell_id", ""))
    params = _case_parameters(plan, case_id)
    scene = construct(case_id, direction=params["direction"],
                      area_blocked=params["area_blocked"],
                      sidewalk_end=params["sidewalk_end_m"],
                      obstruction_kind=params["obstruction_kind"])
    design_receipt = audit_design(scene)
    if survey.get("cell_id") != plan["cell_id"] or survey.get("layout") != "hill_crest":
        raise ValueError("site survey does not match exact cell")
    if scene.obstruction_kind == "missing_section":
        interval = [20, scene.sidewalk_end]
        if interval not in survey.get("observed_missing_sidewalk_intervals_local_m", []):
            raise ValueError("missing sidewalk section absent from original survey")
    owned = []
    try:
        if scene.obstruction_kind == "impassable_section":
            owned.append(adapter.spawn_obstacle(scene.obstacles[0], survey["local_to_world"]))
        else:
            adapter.verify_existing_gap(scene.missing_sections[0], survey["local_to_world"])
        if scene.area_blocked:
            barrier = next(o for o in scene.obstacles if o.name == "intervening_barrier")
            owned.append(adapter.spawn_obstacle(barrier, survey["local_to_world"]))
        walker = adapter.spawn_pedestrian(scene.route[0], survey["local_to_world"])
        owned.append(walker)
        adapter.set_pedestrian_route(walker, scene.route, survey["local_to_world"])
        readback = adapter.readback(walker, tuple(owned), survey["map_id"])
        if readback.get("map_id") != survey["map_id"] or not readback.get("walker_spawned"):
            raise ValueError("Native actor readback failed")
        if readback.get("obstacle_count") != len(scene.obstacles):
            raise ValueError("Native obstacle readback differs from construction")
        return {"case_id": case_id, "design": design_receipt, "owned_handles": owned,
                "native_readback": readback, "site_map_id": survey["map_id"],
                "route_local_xy_m": [list(point) for point in scene.route],
                "survey_sha256": survey_sha256}
    except Exception:
        for handle in reversed(owned):
            adapter.destroy(handle)
        raise
