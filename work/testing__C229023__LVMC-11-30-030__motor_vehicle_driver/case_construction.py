"""Source-bound construction selection for the six fixed crosswalk cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from crosswalk_construction import build_sourced
from crosswalk_measurements import ASSIGNMENT_ID


CASES = {
    "unmarked_wait": ("unmarked", "wait", "permit_pedestrian"),
    "unmarked_pass": ("unmarked", "pass", "permit_pedestrian"),
    "marked_wait": ("marked", "wait", "permit_pedestrian"),
    "marked_pass": ("marked", "pass", "permit_pedestrian"),
    "unmarked_other_stop_wait": ("unmarked", "wait", "other"),
    "unmarked_other_stop_pass": ("unmarked", "pass", "other"),
}


def construct(site_path: str | Path, case_id: str, *, plan_path: str | Path | None = None) -> dict:
    prefix = ASSIGNMENT_ID + "__"
    if not case_id.startswith(prefix) or case_id[len(prefix):] not in CASES:
        raise ValueError("case is not one of the six exact crosswalk constructions")
    if plan_path is None:
        plan_path = Path(__file__).with_name("case-plan.json")
    plan_raw = Path(plan_path).read_bytes()
    plan = json.loads(plan_raw)
    if plan.get("assignment_id") != ASSIGNMENT_ID or case_id not in {c["case_id"] for c in plan.get("cases", [])}:
        raise ValueError("case is absent from the exact case plan")
    crossing, behavior, purpose = CASES[case_id[len(prefix):]]
    site = Path(site_path)
    geometry = build_sourced(site, crosswalk_kind=crossing, ego_behavior=behavior)
    purpose_source = site.parent / geometry["source_inventory"]["stopped_purpose"]["path"]
    observed_purpose = json.loads(purpose_source.read_bytes())
    if observed_purpose.get("source_kind") != "original_observer_statement" or observed_purpose.get("lead_stop_purpose") != purpose:
        raise ValueError("original lead stop purpose differs from exact case")
    geometry.update({"case_id": case_id, "lead_stop_purpose": purpose,
                     "case_plan_sha256": hashlib.sha256(plan_raw).hexdigest(),
                     "capture_plan": {"fps": 20, "frames": 900,
                                      "cameras": ["overview", "approach", "reference_corner", "driver_reference"]},
                     "physical_acceptance_claimed": False, "legal_judgment": "unresolved"})
    return geometry


def compare_constructions(left: dict, right: dict, comparison_id: str,
                          *, plan_path: str | Path | None = None) -> dict:
    """Check declared changes against two source-bound construction proposals."""
    if plan_path is None:
        plan_path = Path(__file__).with_name("case-plan.json")
    plan_raw = Path(plan_path).read_bytes()
    plan = json.loads(plan_raw)
    pairs = {c["comparison_id"]: c["case_ids"] for c in plan.get("comparisons", [])}
    if comparison_id not in pairs or [left.get("case_id"), right.get("case_id")] != pairs[comparison_id]:
        raise ValueError("comparison requires its exact ordered case pair")
    expected_hash = hashlib.sha256(plan_raw).hexdigest()
    for proposal in (left, right):
        if proposal.get("assignment_id") != ASSIGNMENT_ID or proposal.get("case_plan_sha256") != expected_hash:
            raise ValueError("comparison proposal is not bound to the current case plan")
        if proposal.get("physical_acceptance_claimed") is not False or proposal.get("legal_judgment") != "unresolved":
            raise ValueError("comparison proposal asserts a physical or legal conclusion")
    if left.get("map_id") != right.get("map_id") or left.get("capture_plan") != right.get("capture_plan"):
        raise ValueError("comparison changed map or capture conditions")
    for key in ("lead_stop_center", "pedestrian_route"):
        if left.get(key) != right.get(key):
            raise ValueError(f"comparison changed fixed {key}")
    allowed = {"ego_behavior"} if comparison_id != "crosswalk_kind" and comparison_id != "stop_purpose" else ({"crosswalk_kind"} if comparison_id == "crosswalk_kind" else {"lead_stop_purpose"})
    for key in ("crosswalk_kind", "ego_behavior", "lead_stop_purpose"):
        if key in allowed:
            if left.get(key) == right.get(key):
                raise ValueError(f"comparison did not vary {key}")
        elif left.get(key) != right.get(key):
            raise ValueError(f"comparison changed fixed {key}")
    if comparison_id != "crosswalk_kind" and left.get("crosswalk_polygon") != right.get("crosswalk_polygon"):
        raise ValueError("comparison changed fixed crossing geometry")
    if comparison_id == "stop_purpose" and left.get("ego_route") != right.get("ego_route"):
        raise ValueError("comparison changed fixed ego route")
    fixed_sources = {"map", "intersection", "sidewalk", "curb_or_edge", "stopped_purpose"}
    if comparison_id == "stop_purpose":
        fixed_sources.remove("stopped_purpose")
    if left.get("crosswalk_kind") == right.get("crosswalk_kind") == "marked":
        fixed_sources.add("marking")
    for name in fixed_sources:
        if left["source_inventory"].get(name) != right["source_inventory"].get(name):
            raise ValueError(f"comparison changed fixed {name} source")
    return {"comparison_id": comparison_id, "case_ids": pairs[comparison_id],
            "fixed_source_names_checked": sorted(fixed_sources),
            "physical_acceptance_claimed": False, "legal_judgment": "unresolved"}
