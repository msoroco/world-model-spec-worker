"""Distinct unselected construction plans and measurable Native retry triggers."""
from __future__ import annotations

import hashlib
import json
from geometry import OBSERVER_DISTANCES_FT, obstruction_radius_for_limit

CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def plan(suffix: str, candidate: str) -> dict:
    if suffix not in OBSERVER_DISTANCES_FT or candidate not in CANDIDATES:
        raise ValueError('Unknown C104538 case or candidate')
    limit = OBSERVER_DISTANCES_FT[suffix]
    knobs = {
        'opendrive_vertex_distance_m': 0.1 if candidate == 'fallback1' else 0.25,
        'obstruction_segment_length_m': 1.0 if candidate == 'fallback2' else 2.0,
        'reference_camera_height_m': 6.0 if candidate == 'fallback3' else 4.0,
        'ego_camera_height_m': 2.2,
        'sample_rate_hz': 20,
        'duration_s': 24,
    }
    trigger = {
        'primary': None,
        'fallback1': {
            'source': 'original Native map waypoint/elevation readback',
            'metric': 'maximum crest mesh height error against authored profile, m',
            'condition': '> 0.15 m',
            'status': 'unmeasured_physical'},
        'fallback2': {
            'source': 'original Native obstruction actor polygon/readback',
            'metric': 'maximum radial gap in inner obstruction, m',
            'condition': '> 0.05 m',
            'status': 'unmeasured_physical'},
        'fallback3': {
            'source': 'independent original-pixel visibility audit at 500 ft, both directions',
            'metric': 'fraction of target body/pixel frames with audited line of sight',
            'condition': '< 0.95',
            'status': 'unmeasured_physical'},
    }[candidate]
    construction = {
        'format': 'c104538-unselected-construction-plan-v1',
        'case_suffix': suffix, 'candidate_id': candidate,
        'law_id': 'NRS-484B-407', 'cell_id': 'C104538',
        'actor': 'motor_vehicle_driver',
        'authored_reference_limit_ft': limit,
        'authored_obstruction_radius_m': obstruction_radius_for_limit(limit),
        'knobs': knobs, 'retry_trigger': trigger,
        'native_attempt_executed': False,
        'physical_trigger_measured': False,
        'selected': False,
    }
    construction['construction_sha256'] = hashlib.sha256(
        json.dumps(construction,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return construction


def check() -> dict:
    all_plans = {(suffix,candidate):plan(suffix,candidate)
                 for suffix in OBSERVER_DISTANCES_FT for candidate in CANDIDATES}
    assert len({item['construction_sha256'] for item in all_plans.values()}) == 12
    for suffix in OBSERVER_DISTANCES_FT:
        candidates = [all_plans[(suffix,c)] for c in CANDIDATES]
        fixed = ('law_id','cell_id','actor','authored_reference_limit_ft',
                 'authored_obstruction_radius_m')
        for key in fixed:
            assert len({item[key] for item in candidates}) == 1
        knobs = [item['knobs'] for item in candidates]
        for fallback in knobs[1:]:
            assert sum(fallback[key] != knobs[0][key] for key in knobs[0]) == 1
        assert all(item['retry_trigger']['status']=='unmeasured_physical'
                   for item in candidates[1:])
    return {'passed':True,'cases':3,'construction_plans':12,
            'distinct_fallbacks_per_case':3,
            'measured_physical_fallback_triggers':0,
            'native_executed':False}
