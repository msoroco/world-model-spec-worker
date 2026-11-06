"""Independent fixed-condition and fallback-distinction audit for steady witnesses."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')
cases = {}
for suffix in ('witness_1', 'witness_2'):
    plans = [json.loads((HERE / 'draft-candidates' / suffix / ident / 'construction.json').read_text())
             for ident in IDS]
    assert [plan['candidate_id'] for plan in plans] == list(IDS)
    assert all(plan['case_id'] == HERE.name + '__' + suffix for plan in plans)
    assert all((plan['law_id'], plan['cell_id'], plan['actor'], plan['duration_s'], plan['rate_hz']) ==
               ('NRS-484B-283-1d4', 'C10316', 'pedestrian', 12, 20) for plan in plans)
    assert len({json.dumps(plan['engineering'], sort_keys=True) for plan in plans}) == 4
    original = plans[0]['engineering']
    expected_changes = ({'spawn_start_x_m', 'pre_roll_s'}, {'clock_mode'},
                        {'display_camera_distance_m'})
    for plan, changed in zip(plans[1:], expected_changes):
        knobs = plan['engineering']
        assert {key for key in original if knobs[key] != original[key]} == changed
        assert plan['trigger']['source'] != 'none'
        assert plan['trigger']['threshold'] is not None
    assert all(plan['engineering']['display_camera_width'] == 1280 and
               plan['engineering']['display_camera_height'] == 720 for plan in plans)
    cases[suffix] = plans
for a, b in zip(cases['witness_1'], cases['witness_2']):
    x, y = a['engineering'], b['engineering']
    assert {key for key in x if x[key] != y[key]} == {'steady_start_s'}
assert [cases[suffix][0]['engineering']['steady_start_s'] for suffix in cases] == [4.0, .5]
print(json.dumps({'audit': 'pass', 'unselected_candidate_plans': 8,
                  'distinct_fallbacks_per_case': 3, 'physical_triggers_measured': 0,
                  'selected_cases': 0}))
