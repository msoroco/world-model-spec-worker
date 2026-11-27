"""Audit one authored statutory branch contrast without assigning a legal label."""
from __future__ import annotations

import json
from pathlib import Path

from branch_context import ACTIVITIES, EXCEPTIONS

FIXED = ("law_id", "cell_id", "actor", "road_geometry_sha256", "obstruction_geometry_sha256",
         "obstruction_kind", "camera_profile", "duration_s", "frame_rate_hz",
         "park_y_m", "passing_controller")


def audit(left_path: Path, right_path: Path, axis: str) -> dict:
    left = json.loads(Path(left_path).read_text())
    right = json.loads(Path(right_path).read_text())
    if axis not in ("activity_request", "exception_request"):
        raise ValueError("Unknown statutory comparison axis")
    if left.get("case_id") == right.get("case_id"):
        raise ValueError("Comparison needs two exact cases")
    if any(left.get(name) != right.get(name) or left.get(name) is None for name in FIXED):
        raise ValueError("Statutory branch comparison changed a fixed physical condition")
    if left.get("activity_request") not in ACTIVITIES or right.get("activity_request") not in ACTIVITIES:
        raise ValueError("Activity source request missing")
    if left.get("exception_request") not in EXCEPTIONS | {None} or right.get("exception_request") not in EXCEPTIONS | {None}:
        raise ValueError("Exception source request missing")
    if left.get(axis) == right.get(axis):
        raise ValueError("Statutory branch comparison axis did not change")
    other = "exception_request" if axis == "activity_request" else "activity_request"
    if left.get(other) != right.get(other):
        raise ValueError("Statutory branch comparison changed two axes")
    for item in (left, right):
        if item.get("source_gate_passed") is not True or not item.get("source_gate_sha256"):
            raise ValueError("Comparison lacks original source gate receipt")
        if item.get("physical_acceptance_claimed") is not False or item.get("legal_acceptance_claimed") is not False:
            raise ValueError("Comparison asserts an unsupported outcome")
    return {"format": "c135702-branch-comparison", "case_ids": [left["case_id"], right["case_id"]],
            "axis": axis, "source_gates": [left["source_gate_sha256"], right["source_gate_sha256"]],
            "fixed_conditions": list(FIXED), "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False, "comparison_recorded": True}
