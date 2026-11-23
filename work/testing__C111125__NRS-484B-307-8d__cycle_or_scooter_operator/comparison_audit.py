"""Independent fixed-condition audit of saved bicycle signal measurements."""
from __future__ import annotations


class ComparisonError(ValueError):
    pass


PAIRS = {
    "two_vs_one_complete_cycles": ("two_cycles_failed_detection", "one_cycle", "complete_device_cycles_before_entry"),
    "failed_detection_vs_signal_change": ("two_cycles_failed_detection", "signal_changes", "detector_failure_observed"),
    "stop_antecedent": ("two_cycles_failed_detection", "no_prior_stop", "prior_stop_observed"),
    "yield_to_directed_participant": ("two_cycles_failed_detection", "fails_to_yield", "conflict_at_entry"),
}


def audit_pair(comparison_id: str, left: dict, right: dict) -> dict:
    if comparison_id not in PAIRS:
        raise ComparisonError("unknown comparison")
    a, b, different = PAIRS[comparison_id]
    if (left.get("case_suffix"), right.get("case_suffix")) != (a, b):
        raise ComparisonError("wrong exact case pair")
    fixed = ("map_sha256", "device_sha256", "detector_sha256", "blueprint_sha256")
    for key in fixed:
        if not left.get(key) or left[key] != right.get(key):
            raise ComparisonError("fixed source differs: " + key)
    for row in (left, right):
        if not row.get("source_sha256") or len(row["source_sha256"]) != 4:
            raise ComparisonError("missing original source bindings")
        if not row.get("straight_route_observed") or not isinstance(row.get("entry_frame"), int):
            raise ComparisonError("original straight entry absent")
        if row.get("duration_frames", 0) <= row["entry_frame"]:
            raise ComparisonError("entry outside original trace")
    base = ("prior_stop_observed", "red_held_to_entry", "detector_occupancy_observed", "detector_failure_observed", "conflict_at_entry")
    for key in base:
        if key != different and left.get(key) != right.get(key):
            # A signal change entails a changed detector output; this is its
            # single causal comparison, not a second independent intervention.
            if comparison_id == "failed_detection_vs_signal_change" and key == "red_held_to_entry":
                continue
            raise ComparisonError("undeclared measured difference: " + key)
    if different == "complete_device_cycles_before_entry":
        if not (left.get(different, 0) >= 2 and right.get(different) == 1):
            raise ComparisonError("two-versus-one cycles not measured")
    elif different == "conflict_at_entry":
        if (left.get(different), right.get(different)) != (False, True):
            raise ComparisonError("yield difference not measured")
    elif (left.get(different), right.get(different)) != (True, False):
        raise ComparisonError("declared difference not measured")
    if not left.get("prior_stop_observed") or not left.get("red_held_to_entry") or not left.get("detector_failure_observed") or left.get("complete_device_cycles_before_entry", 0) < 2 or left.get("conflict_at_entry"):
        raise ComparisonError("reference case prerequisites not evidenced")
    return {"comparison_id": comparison_id, "fixed_sources_checked": len(fixed),
            "independent_original_sources_checked": True, "physical_acceptance": False,
            "legal_verdict": None}
