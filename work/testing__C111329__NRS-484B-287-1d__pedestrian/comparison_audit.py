"""Reject incomplete or confounded saved crossing comparisons."""

FIXED = ("map_sha256", "intersection_polygon", "walker_blueprint_id", "camera_contract_sha256", "duration_frames", "fps")


def audit(left: dict, right: dict, comparison: str) -> dict:
    if comparison not in {"diagonal_path_without_authority", "diagonal_device_authority", "authorized_device_path_control"}:
        raise ValueError("unknown comparison")
    for case in (left, right):
        for field in (*FIXED, "original_measurement", "device_inventory_sha256"):
            if field not in case or case[field] in (None, ""):
                raise ValueError(f"missing source-bound comparison field: {field}")
        if case["fps"] != 20 or case["duration_frames"] < 2:
            raise ValueError("capture contract mismatch")
        if not case["original_measurement"].get("walker_id") or not case["original_measurement"].get("device_source_hashes"):
            raise ValueError("original walker/device source missing")
    for field in FIXED:
        if left[field] != right[field]:
            raise ValueError(f"fixed condition differs: {field}")
    if comparison == "diagonal_device_authority":
        if left["route_kind"] != right["route_kind"] or left["route_kind"] != "opposite":
            raise ValueError("device comparison route changed")
        if left["authorization_observed"] == right["authorization_observed"]:
            raise ValueError("device authorization did not vary")
    else:
        if left["device_inventory_sha256"] != right["device_inventory_sha256"] or left["authorization_observed"] != right["authorization_observed"]:
            raise ValueError("route comparison device condition changed")
        if left["route_kind"] == right["route_kind"]:
            raise ValueError("route kind did not vary")
    return {"comparison_id": comparison, "passed": True, "case_ids": [left["case_id"], right["case_id"]]}


def audit_saved_pair(left_attempt, left_refs, right_attempt, right_refs, comparison, *, expected_frames=900, allow_diagnostic=False):
    """Reopen two original attempts and require the exact planned contrast."""
    import hashlib
    import json
    from pathlib import Path
    from delivery_audit import audit as audit_delivery
    from saved_process import ASSIGNMENT, CASES, _read

    expected = {
        'diagonal_path_without_authority': ('adjacent_no_diagonal_authority', 'diagonal_no_authority'),
        'diagonal_device_authority': ('diagonal_no_authority', 'diagonal_authorized'),
        'authorized_device_path_control': ('diagonal_authorized', 'adjacent_authorized_device'),
    }
    if comparison not in expected:
        raise ValueError('unknown exact C111329 comparison')
    if len(left_refs) != 4 or len(right_refs) != 4:
        raise ValueError('site, Native, camera and saved source references required')
    case_ids = [ASSIGNMENT + '__' + suffix for suffix in expected[comparison]]
    roots = [Path(left_attempt).resolve(strict=True), Path(right_attempt).resolve(strict=True)]
    refs = [left_refs, right_refs]
    audits = [audit_delivery(root, case_id, *source_refs, expected_frames=expected_frames, allow_diagnostic=allow_diagnostic) for root, case_id, source_refs in zip(roots, case_ids, refs)]
    sites = [_read(root, source_refs[0]) for root, source_refs in zip(roots, refs)]
    natives = [_read(root, source_refs[1]) for root, source_refs in zip(roots, refs)]
    saved = [_read(root, source_refs[3]) for root, source_refs in zip(roots, refs)]
    for i in range(2):
        if audits[i]['case_id'] != case_ids[i] or (audits[i]['diagnostic'] is not False and not allow_diagnostic):
            raise ValueError('comparison requires exact original Native deliveries')
        if saved[i]['measurement']['route_kind_planned'] != CASES[expected[comparison][i]][0]:
            raise ValueError('measured crossing route differs from planned case')
    if (sites[0]['map_sha256'] != sites[1]['map_sha256'] or
            sites[0]['intersection_polygon'] != sites[1]['intersection_polygon'] or
            sites[0]['corners'] != sites[1]['corners']):
        raise ValueError('fixed intersection geometry differs')
    if (audits[0]['frame_count'] != audits[1]['frame_count'] or
            saved[0]['media_audit']['camera_dimensions'] != saved[1]['media_audit']['camera_dimensions']):
        raise ValueError('fixed capture contract differs')
    if (natives[0].get('fps') != natives[1].get('fps') or
            natives[0].get('walker_blueprint_id') != natives[1].get('walker_blueprint_id')):
        raise ValueError('fixed pedestrian blueprint or frame rate differs')
    if not allow_diagnostic:
        blueprints = [row['rows'][0].get('actor_state', {}).get('blueprint') for row in natives]
        if not blueprints[0] or blueprints[0] != blueprints[1]:
            raise ValueError('fixed original pedestrian blueprint differs')
    if comparison == 'diagonal_device_authority':
        if (natives[0]['device_inventory_sha256'] == natives[1]['device_inventory_sha256'] or
                saved[0]['measurement']['authorization_observed_during_inside'] is True or
                saved[1]['measurement']['authorization_observed_during_inside'] is not True):
            raise ValueError('source-measured diagonal authorization contrast missing')
    else:
        if (natives[0]['device_inventory_sha256'] != natives[1]['device_inventory_sha256'] or
                saved[0]['measurement']['authorization_observed_during_inside'] !=
                saved[1]['measurement']['authorization_observed_during_inside']):
            raise ValueError('fixed official device source or state differs')
    return {'format': 'c111329-independent-comparison-audit-v1',
            'comparison_id': comparison, 'case_ids': case_ids,
            'delivery_audit_sha256': [hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest() for row in audits],
            'fixed_original_map_sha256': sites[0]['map_sha256'],
            'measured_route_kinds': [row['measurement']['route_kind_planned'] for row in saved],
            'observed_diagonal_authorization': [row['measurement']['authorization_observed_during_inside'] for row in saved],
            'exception_484B_290': 'unresolved', 'legal_verdict': None}
