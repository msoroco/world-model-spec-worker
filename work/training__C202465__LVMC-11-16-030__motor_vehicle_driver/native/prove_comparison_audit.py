"""Synthetic interface fixture for independent comparison rejection branches."""

import json
from pathlib import Path

from comparison_audit import audit
from prove_rail_scene import SIGHT_BLOCKERS, crossing, make_rows


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


plan = json.loads((Path(__file__).resolve().parents[1] / 'case-plan.json').read_text())
designs = {c['case_id']: c['construction_design'] for c in plan['cases']}
axis = {
    'speed_15_mph': 'speed', 'left_sight': 'sight', 'right_sight': 'sight',
    'crossing_view': 'sight', 'flagman_exception': 'flagman',
    'inactive_signal_exception': 'signal_state', 'signal_indication': 'signal_state',
    'signal_visibility': 'signal_visibility',
}


def packet(case_id):
    design = designs[case_id]
    state = design['exception_state']
    refs = [b['source_ref'] for b in SIGHT_BLOCKERS[design['sight_mode']]]
    return {'case_id': case_id, 'crossing': crossing,
            'source_metadata': {
                'road_sha256': 'a'*64, 'railway_review_sha256': 'b'*64,
                'approach_review_sha256': 'c'*64, 'camera_plan_sha256': 'd'*64,
                'ego_blueprint': 'vehicle.fixture', 'rail_vehicle_actor_ids': [2, 3],
                'crossing_source_ref': 'fixture:crossing',
                'flagman_source_ref': 'fixture:flagman', 'signal_source_ref': 'fixture:signal',
                'blocker_source_refs': refs, 'diagnostic_fixture': False},
            'rows': make_rows(design['speed_mode'], SIGHT_BLOCKERS[design['sight_mode']],
                              duty=state == 'flagman_on_duty',
                              inactive=state == 'visible_inactive_signal',
                              active=state == 'visible_active_signal',
                              installed_not_visible=state == 'installed_not_visible')}


for comparison in plan['comparisons']:
    name = comparison['comparison_id'].split('__')[-1]
    spec = dict(comparison, axis=axis[name])
    a, b = (packet(cid) for cid in spec['case_ids'])
    result = audit(a, b, spec)
    assert result['axis'] == axis[name]
    assert result['physical_acceptance_claimed'] is False
    reject(lambda: audit(dict(a, source_metadata=dict(a['source_metadata'],
                                                       camera_plan_sha256='e'*64)), b, spec),
           'fixed original source')
    reject(lambda: audit(dict(a, source_metadata=dict(a['source_metadata'],
                                                       diagnostic_fixture=True)), b, spec),
           'diagnostic fixture')
    reject(lambda: audit(a, b, dict(spec, case_ids=list(reversed(spec['case_ids'])))),
           'case identity')
print('PASS: eight source-bound comparison axes and stale/missing-source rejection paths')
