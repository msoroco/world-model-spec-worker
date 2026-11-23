"""Independent source-join audit for one measured intersection comparison.

This checks source completeness and experimental isolation, not statutory status.
"""

from intersection_observables import SourceError


def audit(comparison: dict, left: dict, right: dict) -> dict:
    ids = comparison.get("case_ids", [])
    if len(ids) != 2 or [left.get("case_id"), right.get("case_id")] != ids:
        raise SourceError("comparison case identity differs")
    for name, record in (("left", left), ("right", right)):
        if not all(record.get("source_seals", {}).get(k) for k in ("boundary", "trace", "activity")):
            raise SourceError(f"{name} original source seals missing")
        if not record.get("frames") or not record.get("source_refs"):
            raise SourceError(f"{name} original observations missing")
    if left.get("map_id") != right.get("map_id") or left.get("source_seals", {}).get("boundary") != right.get("source_seals", {}).get("boundary"):
        raise SourceError("reviewed intersection boundary differs")
    left_conditions = left.get("condition_receipt", {})
    right_conditions = right.get("condition_receipt", {})
    fixed = comparison.get("fixed_condition_keys", [])
    changed = comparison.get("difference_keys", [])
    if not fixed or not changed:
        raise SourceError("comparison measurement contract missing")
    for key in fixed:
        if key not in left_conditions or key not in right_conditions:
            raise SourceError(f"fixed condition source missing: {key}")
        if left_conditions[key] != right_conditions[key]:
            raise SourceError(f"fixed condition differs: {key}")
    observed = []
    for key in changed:
        if key not in left_conditions or key not in right_conditions:
            raise SourceError(f"deliberate difference source missing: {key}")
        if left_conditions[key] != right_conditions[key]:
            observed.append(key)
    if not observed:
        raise SourceError("declared deliberate difference not observed")
    return {"format": "intersection-comparison-audit-v1",
            "comparison_id": comparison.get("comparison_id"), "case_ids": ids,
            "fixed_conditions_verified": fixed, "observed_difference_keys": observed,
            "legal_conclusion": None}
