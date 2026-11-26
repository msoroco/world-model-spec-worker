"""Source-gated scene for a bounded engineering speed request.

This extends an existing reviewed scene without changing its selected bundle
or implying that a setpoint was realized or is a legal boundary.
"""
from __future__ import annotations

import re
from pathlib import Path

from build_engineering_sweep_preview import AXES
from reviewed_scene import ASSIGNMENT, plan


def engineering_station(case_id: str) -> tuple[str, str, float] | None:
    for axis, (anchor, variable, _observable, values) in AXES.items():
        match = re.fullmatch(re.escape(ASSIGNMENT + "__" + axis) + r"-000([0-2])", case_id)
        if match:
            order = (values[0], values[-1], values[1])
            role = "ego" if variable == "ego_speed_mps" else "slower_vehicle"
            return anchor, role, order[int(match.group(1))]
    return None


def plan_engineering(authority_root: Path, site_ref: dict, case_id: str) -> dict:
    station = engineering_station(case_id)
    if station is None:
        raise ValueError("unassigned exact engineering case")
    anchor, role, requested = station
    scene = plan(authority_root, site_ref, ASSIGNMENT + "__" + anchor)
    scene["case_id"] = case_id
    next(actor for actor in scene["actors"] if actor["role"] == role)["target_speed_mps"] = requested
    scene["engineering_setpoint"] = {
        "actor_role": role, "requested_speed_mps": requested,
        "legal_threshold": None, "realized_speed_mps": None,
    }
    return scene
