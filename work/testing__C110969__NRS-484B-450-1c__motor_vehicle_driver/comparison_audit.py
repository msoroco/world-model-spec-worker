"""Independent source-join audit for one measured intersection comparison.

This checks source completeness and experimental isolation, not statutory status.
"""

from intersection_observables import SourceError


REVIEWED_KEYS = ('activity', 'traffic_conflict', 'law_direction',
                 'officer_direction', 'device_direction', 'motion_history')


def original_condition_record(attempt, case_id):
    """Bind independently reviewed conditions to original sealed Native sources.

    A reviewer must provide observed condition values and point each one to a
    source in the completed capture. Controller intent is never substituted.
    """
    import hashlib
    import json
    from pathlib import Path
    from delivery_audit import audit as audit_delivery
    from finalize_observables import finalize

    attempt = Path(attempt).resolve()
    delivery = audit_delivery(attempt, case_id)
    if delivery['canonical_delivery_acceptance'] != 'source_verified':
        raise SourceError('original delivery source audit required for comparison')
    original = finalize(attempt/'source-manifest.json')
    route = json.loads((attempt/'reviewed-route.json').read_text())
    review = json.loads((attempt/'condition-review.json').read_text())
    seal = json.loads((attempt/'capture-seal.json').read_text())
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if (review.get('case_id') != case_id or
            review.get('independent_review') is not True or not review.get('reviewer') or
            not review.get('review_note') or route.get('case_id') != case_id):
        raise SourceError('independent exact-case condition review missing')
    for name in ('capture-seal.json', 'source-manifest.json', 'reviewed-route.json'):
        if review.get('source_sha256', {}).get(name) != sha(attempt/name):
            raise SourceError('condition review source differs: '+name)
    if len(original['frames']) != 900 or len(delivery['videos']) != 4:
        raise SourceError('complete original comparison interval missing')
    conditions = {
        'map_id': original['map_id'],
        'intersection_boundary_sha256': original['source_seals']['boundary'],
        'vehicle_blueprint': route['vehicle_blueprint'],
        'approach_lane': route['approach_lane'],
        'camera_profile': 'four-original-rgb-20hz-900frames',
        'duration_frames': 900,
        'destination': ('inside' if original['frames'][-1]['within_or_touching_boundary']
                        else 'outside'),
    }
    for key in REVIEWED_KEYS:
        value = review.get('conditions', {}).get(key)
        ref = review.get('field_sources', {}).get(key, {})
        name = ref.get('path', '')
        path = (attempt/name).resolve()
        if (not isinstance(name, str) or not name or not path.is_relative_to(attempt)
                or not path.is_file() or seal.get('sources', {}).get(name) != sha(path)
                or ref.get('sha256') != sha(path) or value in (None, '', 'unresolved')):
            raise SourceError('independent original condition source missing: '+key)
        conditions[key] = value
    return {'case_id': case_id, 'map_id': original['map_id'],
            'source_seals': original['source_seals'],
            'source_refs': original['source_refs'], 'frames': original['frames'],
            'condition_receipt': conditions,
            'condition_review_sha256': sha(attempt/'condition-review.json'),
            'legal_conclusion': None}


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
