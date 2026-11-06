"""Independent candidate and synthetic trigger source audit."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from engineering import synthetic_trigger_metrics


def main():
    summary = json.loads((HERE / 'draft-countdown-measurement-summary.json').read_text())
    root = Path(summary['retained_root'])
    candidates = {}
    for suffix in ('probe_01', 'probe_02'):
        plans = {}
        for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            plan = json.loads((HERE / 'draft-candidates' / suffix / ident / 'construction.json').read_text())
            assert plan['case_id'].endswith(suffix) and plan['candidate_id'] == ident
            assert plan['law_id'] == 'NRS-484B-283-1d2' and plan['cell_id'] == 'C10316'
            assert plan['actor'] == 'pedestrian' and (plan['duration_s'], plan['rate_hz']) == (12, 20)
            assert plan['status'] == 'unselected_cpu_construction_plan_no_native_display_proof'
            plans[ident] = plan
        base = plans['primary']['engineering']
        changed = {ident: {key for key in base if plans[ident]['engineering'][key] != base[key]}
                   for ident in ('fallback1', 'fallback2', 'fallback3')}
        assert changed == {'fallback1': {'spawn_start_x_m', 'pre_roll_s'},
                           'fallback2': {'clock_mode'},
                           'fallback3': {'display_camera_distance_m'}}
        assert len({p['trigger']['source'] for ident, p in plans.items() if ident != 'primary'}) == 3
        assert all(p['engineering']['countdown_zero_s'] == (10 if suffix == 'probe_01' else 7)
                   for p in plans.values())
        metrics = synthetic_trigger_metrics(root / suffix)
        assert metrics['spawn_clearance_m'] == .88 and metrics['spawn_clearance_below_1_25_m'] is True
        assert metrics['original_display_phase_skew_ms'] is None
        assert metrics['original_countdown_legibility_fraction'] is None
        candidates[suffix] = plans
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = dict(candidates['probe_01'][ident]['engineering'])
        b = dict(candidates['probe_02'][ident]['engineering'])
        assert a.pop('countdown_zero_s') == 10 and b.pop('countdown_zero_s') == 7
        assert a == b
    print(json.dumps({'unselected_candidate_plans': 8, 'distinct_fallbacks_per_case': 3,
                      'controlled_difference': 'countdown_zero_s',
                      'synthetic_spawn_clearance_m': .88,
                      'physically_measured_triggers': 0, 'selected_cases': 0}))


if __name__ == '__main__':
    main()
