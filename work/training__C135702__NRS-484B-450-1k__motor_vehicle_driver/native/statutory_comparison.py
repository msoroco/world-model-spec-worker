"""Independent request-axis audit for source-shaped statutory diagnostics."""
from __future__ import annotations

import json
from pathlib import Path

from statutory_variants import KINDS, POSITIONS
from branch_context import ACTIVITIES, EXCEPTIONS

AXES = ("activity_request", "placement_request", "obstruction_kind_request", "exception_request")
FIXED = ("law_id", "cell_id", "actor", "road_geometry_sha256",
         "camera_profile", "duration_s", "rate_hz", "passing_controller")


def audit(left_path: Path, right_path: Path, axis: str) -> dict:
    if axis not in AXES:
        raise ValueError("Unknown statutory request axis")
    left, right = (json.loads(Path(path).read_text()) for path in (left_path, right_path))
    if left.get("case_id") == right.get("case_id"):
        raise ValueError("Two different exact cases required")
    for key in FIXED:
        if left.get(key) is None or left[key] != right.get(key):
            raise ValueError("Fixed comparison condition changed: " + key)
    if axis == "obstruction_kind_request":
        if not left.get("surface_profile_sha256") or not right.get("surface_profile_sha256") or left["surface_profile_sha256"] == right["surface_profile_sha256"]:
            raise ValueError("Excavation comparison lacks distinct surface source")
    elif left.get("surface_profile_sha256") != right.get("surface_profile_sha256"):
        raise ValueError("Fixed comparison surface changed")
    domains = {"activity_request": ACTIVITIES,
               "placement_request": set(POSITIONS),
               "obstruction_kind_request": KINDS,
               "exception_request": EXCEPTIONS | {None}}
    for key, allowed in domains.items():
        if left.get(key) not in allowed or right.get(key) not in allowed:
            raise ValueError("Missing statutory request: " + key)
        if (left[key] == right[key]) == (key == axis):
            raise ValueError("Comparison did not isolate one statutory request axis")
    for item in (left, right):
        if item.get("source_gate_passed") is not True or not item.get("source_gate_sha256"):
            raise ValueError("Original source gate missing")
        if item.get("source_gate_kind") not in {"synthetic_cpu", "original_native"}:
            raise ValueError("Source gate provenance missing")
        if item.get("physical_acceptance_claimed") is not False or item.get("legal_acceptance_claimed") is not False:
            raise ValueError("Unverified outcome asserted")
    return {"format": "c135702-statutory-comparison-draft",
            "case_ids": [left["case_id"], right["case_id"]],
            "axis": axis, "fixed_conditions": list(FIXED),
            "surface_profile_sha256": [left.get("surface_profile_sha256"), right.get("surface_profile_sha256")],
            "source_gates": [left["source_gate_sha256"], right["source_gate_sha256"]],
            "source_gate_kinds": [left["source_gate_kind"], right["source_gate_kind"]],
            "original_capture_attested": all(item["source_gate_kind"] == "original_native"
                                             for item in (left, right)),
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}
