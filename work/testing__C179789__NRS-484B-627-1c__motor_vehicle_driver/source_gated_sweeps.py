"""Prepare source-gated engineering samples for two judgment phrases.

Requested speed and alternate-entry lead are physical coverage coordinates,
never statutory thresholds or proof that an alternate was possible.
"""
from __future__ import annotations

import json
from pathlib import Path

from alternate_route import path
from reviewed_route_scene import _linked, plan as base_plan

ASSIGNMENT = "testing__C179789__NRS-484B-627-1c__motor_vehicle_driver"
SPEED_MPS = (4.0, 6.0, 5.0)
ENTRY_LEAD_M = (40.0, 80.0, 60.0)


def prepare(authority_root: Path, site_ref: dict) -> list[dict]:
    root = Path(authority_root).resolve()
    site = json.loads(_linked(root, site_ref).read_text(encoding="utf-8"))
    controls = site.get("reviewed_control_feasibility", {})
    low, high = controls.get("ego_speed_min_mps"), controls.get("ego_speed_max_mps")
    if (not isinstance(low, (int, float)) or isinstance(low, bool) or
            not isinstance(high, (int, float)) or isinstance(high, bool) or
            low > min(SPEED_MPS) or high < max(SPEED_MPS) or
            not controls.get("source")):
        raise ValueError("reviewed physical speed range missing")
    opportunities = site.get("reviewed_alternate_opportunities", [])
    by_lead = {item.get("entry_lead_m"): item for item in opportunities
               if isinstance(item, dict)}
    if set(ENTRY_LEAD_M) - set(by_lead):
        raise ValueError("reviewed alternate entry geometry and spacing missing")
    for lead in ENTRY_LEAD_M:
        item = by_lead[lead]
        if not item.get("source") or not item.get("restriction_source"):
            raise ValueError("reviewed alternate opportunity source missing")
        path(item.get("alternate_route_xy"), "alternate opportunity")
    plans = []
    for rank, requested in enumerate(SPEED_MPS):
        case_id = ASSIGNMENT + "__impediment-" + str(rank).zfill(4)
        base = base_plan(root, site_ref, ASSIGNMENT + "__alternate_not_selected")
        base.update(case_id=case_id, sweep_id=ASSIGNMENT + "__impediment",
                    requested_ego_speed_mps=requested,
                    engineering_target_only=True, legal_judgment=None)
        plans.append(base)
    for rank, lead in enumerate(ENTRY_LEAD_M):
        case_id = ASSIGNMENT + "__route_possibility-" + str(rank).zfill(4)
        base = base_plan(root, site_ref, ASSIGNMENT + "__alternate_selected")
        base["scene"] = dict(base["scene"],
                             alternate_route_xy=by_lead[lead]["alternate_route_xy"])
        base.update(case_id=case_id, sweep_id=ASSIGNMENT + "__route_possibility",
                    requested_alternate_entry_lead_m=lead,
                    opportunity_source=by_lead[lead]["source"],
                    engineering_target_only=True, legal_judgment=None,
                    possible_route_judgment=None)
        plans.append(base)
    if len({item["case_id"] for item in plans}) != 6:
        raise ValueError("duplicate sweep case identity")
    return plans
