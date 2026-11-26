"""Expand the exact six C227824 requests over reviewed Native source bases.

The caller supplies two source-bound bases: one with no other governing device
and one with the same route plus one independently inventoried official device.
This function never invents authority, geometry or an actor ID.
"""
from __future__ import annotations

from copy import deepcopy


FIXED = ("map_source_sha256", "route_id", "facing_head_id",
         "highway_polygon_xy_m", "camera_placements", "walker_spawn_xyz_m",
         "walker_blueprint_id", "target_xy_m", "speed_mps",
         "fixed_delta_seconds", "planned_frames")


def expand(plan, *, no_device_base, one_device_base):
    cases = plan.get("cases")
    if not isinstance(cases, list) or len(cases) != 9:
        raise ValueError("six branch cases and three sweep cases required")
    for key in FIXED:
        if no_device_base.get(key) != one_device_base.get(key):
            raise ValueError("reviewed fixed source changed across device comparison: " + key)
    if no_device_base.get("governing_pedestrian_device_ids") != []:
        raise ValueError("no-device base has another governing device")
    ids = one_device_base.get("governing_pedestrian_device_ids")
    if not isinstance(ids, list) or len(ids) != 1 or type(ids[0]) is not int:
        raise ValueError("one-device base needs one reviewed actor ID")
    if no_device_base.get("device_inventory_review") == one_device_base.get("device_inventory_review"):
        raise ValueError("different device inventories need distinct review sources")
    result = {}
    expected = {
        "red_no_device_entry": ("none", "entry"),
        "red_no_device_wait": ("none", "wait"),
        "red_walk_entry": ("walk", "entry"),
        "red_countdown_entry": ("flashing_hand_countdown", "entry"),
        "red_flashing_no_countdown_entry": ("flashing_hand_no_countdown", "entry"),
        "red_steady_hand_entry": ("steady_hand", "entry"),
    }
    prefix = plan.get("assignment_id")
    sweep_ids = set()
    for case in cases:
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id.startswith(prefix + "__"):
            raise ValueError("case identity escaped assignment")
        suffix = case_id[len(prefix) + 2:]
        intended = expected.get(suffix)
        if case.get("sweep_id"):
            intended = ("walk", "entry")
            sweep_ids.add(case_id)
        if intended is None or (case.get("other_device_indication"), case.get("entry_request")) != intended:
            raise ValueError("case request differs from exact pedestrian plan")
        if case_id in result:
            raise ValueError("duplicate exact pedestrian case")
        scene = deepcopy(no_device_base if intended[0] == "none" else one_device_base)
        scene.update({"law_id": plan["law_id"], "cell_id": plan["cell_id"],
                      "actor": plan["actor"], "case_id": case_id,
                      "entry_request": intended[1],
                      "requested_pedestrian_indication": intended[0]})
        if case.get("sweep_id"):
            point = case.get("walk_speed_target_mps")
            if type(point) not in (int, float) or point not in (0.8, 1.2, 1.6):
                raise ValueError("engineering walking-speed station missing")
            scene["speed_mps"] = point
        result[case_id] = scene
    if {key[len(prefix) + 2:] for key in result if key not in sweep_ids} != set(expected) or len(sweep_ids) != 3:
        raise ValueError("pedestrian branches or sweep stations incomplete")
    return result
