"""Independently compare source-bound C24757 observations without legal labels."""

import hashlib
import json
from pathlib import Path

from inoperative_stop_measurements import analyze


MODES = ("full_halt_order", "ego_full_halt", "stopping_reference")


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_pair(left, right, mode):
    if mode not in MODES:
        raise ValueError("Named C24757 comparison mode required")
    left, right = Path(left), Path(right)
    a, b = analyze(left), analyze(right)
    ac = json.loads((left / "junction_context.json").read_text())
    bc = json.loads((right / "junction_context.json").read_text())
    fixed = ("native_map_id", "intersection_id", "native_signal_id", "other_native_signal_id",
             "installed_uncovered_vehicular_heads", "intersection_polygon_xy_m",
             "lane_governance_source", "signal_head_video_source")
    if any(ac.get(key) != bc.get(key) for key in fixed):
        raise ValueError("Fixed Native junction or signal context changed")
    if mode != "stopping_reference" and _sha(left / "junction_context.json") != _sha(right / "junction_context.json"):
        raise ValueError("Fixed stopping-reference context changed")
    if mode == "full_halt_order":
        if (not all(a["first_full_halt_before_or_at_selected_boundary"].values()) or
                not all(b["first_full_halt_before_or_at_selected_boundary"].values())):
            raise ValueError("Both vehicles must have observed complete halts")
        def strict_order(report):
            stops = report["first_full_halt_before_or_at_selected_boundary"]
            ego_time, other_time = stops["ego"]["time_s"], stops["other"]["time_s"]
            if ego_time == other_time:
                raise ValueError("Distinct observed full-halt times required")
            return "other_first" if other_time < ego_time else "ego_first"
        left_value, right_value = strict_order(a), strict_order(b)
    elif mode == "ego_full_halt":
        metric = "ego_stopped_before_entry_observed"
        for report in (a, b):
            if not report["first_body_entry"]["ego"]:
                raise ValueError("Ego entry observation required")
        left_value, right_value = a[metric], b[metric]
    else:
        metric = "selected_stop_boundary"
        if not all(report["ego_stopped_before_entry_observed"] for report in (a, b)):
            raise ValueError("Boundary comparison requires observed full stops")
        left_value, right_value = a[metric], b[metric]
    if left_value == right_value:
        raise ValueError("Declared comparison difference is absent")
    return {"format": "worker-inoperative-signal-comparison-audit",
            "mode": mode, "fixed_context_fields": list(fixed),
            "left": {"value": left_value, "source_hashes": a["sources"]},
            "right": {"value": right_value, "source_hashes": b["sources"]},
            "observed_difference": True, "legal_verdict_asserted": False,
            "physical_acceptance_claimed": False}
