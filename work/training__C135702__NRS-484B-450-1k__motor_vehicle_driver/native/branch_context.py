"""Source gates for proposed activity and exception comparison variants.

An authored branch request is a controller target. It never proves an activity,
exception, physical obstruction, or legal consequence. A later Native capture
must copy the independently reviewed original records and retain their hashes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ACTIVITIES = {"stop", "stand", "park"}
EXCEPTIONS = {"traffic_conflict", "law_direction", "police_direction", "traffic_device"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked_record(root: Path, item: dict, expected_kind: str) -> dict:
    if item.get("kind") != expected_kind or item.get("provenance") != "reviewed_original_source":
        raise ValueError("Original reviewed source kind required: " + expected_kind)
    relative = Path(item.get("path", ""))
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Unsafe reviewed source path")
    source = (root / relative).resolve()
    if root.resolve() not in source.parents or not source.is_file() or sha(source) != item.get("sha256"):
        raise ValueError("Reviewed original source missing or changed")
    payload = json.loads(source.read_text())
    if payload.get("source_kind") != expected_kind or not payload.get("original_record_id"):
        raise ValueError("Reviewed original source lacks exact identity")
    return payload


def validate(root: Path, context_path: Path, case_id: str, activity: str,
             exception_request: str | None) -> dict:
    """Validate source links; retain all event and applicability judgments open."""
    if activity not in ACTIVITIES or exception_request not in EXCEPTIONS | {None}:
        raise ValueError("Unknown statutory branch request")
    context = json.loads(context_path.read_text())
    if context.get("case_id") != case_id or context.get("source_kind") != "reviewed_branch_context":
        raise ValueError("Exact case-specific original branch context required")
    activity_source = checked_record(root, context.get("activity_source", {}), "operator_activity")
    if activity_source.get("requested_activity") != activity:
        raise ValueError("Operator activity source does not match branch request")
    authority = context.get("exception_sources", {})
    if set(authority) != EXCEPTIONS:
        raise ValueError("Four separate exception source gates required")
    inspected = {name: checked_record(root, authority[name], name) for name in sorted(EXCEPTIONS)}
    for name, record in inspected.items():
        if record.get("requested_exception") not in (None, name):
            raise ValueError("Exception source mixes statutory branches")
    if exception_request is not None:
        selected = inspected[exception_request]
        if selected.get("requested_exception") != exception_request:
            raise ValueError("Selected exception lacks source-bound request")
        if not selected.get("event_window") or not selected.get("scene_scope"):
            raise ValueError("Selected exception lacks original time or place scope")
        if exception_request in {"police_direction", "traffic_device"} and not selected.get("original_instruction"):
            raise ValueError("Direction branch lacks original instruction")
        if exception_request == "law_direction" and not selected.get("law_citation"):
            raise ValueError("Law exception branch lacks cited legal authority")
        if exception_request == "traffic_conflict" and not selected.get("traffic_source_refs"):
            raise ValueError("Traffic necessity branch lacks original traffic sources")
    return {"format": "c135702-branch-source-gate", "case_id": case_id,
            "activity_request": activity, "exception_request": exception_request,
            "context_sha256": sha(context_path),
            "source_sha256": {"activity": context["activity_source"]["sha256"],
                              **{name: authority[name]["sha256"] for name in sorted(EXCEPTIONS)}},
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "activity_observed": False, "exception_applies": None}
