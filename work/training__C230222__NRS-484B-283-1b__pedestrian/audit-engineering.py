"""Independent invariant audit of unselected curb-entry construction plans."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')
FIXED = ('pedestrian_target_speed_mps', 'vehicle_start_y_m', 'vehicle_target_speed_mps',
         'vehicle_control', 'vehicle_reaction_s', 'vehicle_brake_command',
         'camera_width', 'camera_height')


def audit():
    all_plans = {}
    for suffix, expected_start in (('probe_1', .5), ('probe_2', 3.5)):
        plans = {}
        for ident in IDS:
            path = HERE / 'draft-candidates' / suffix / ident / 'construction.json'
            p = json.loads(path.read_text())
            e = p['engineering']
            if p['case_id'] != 'training__C230222__NRS-484B-283-1b__pedestrian__' + suffix:
                raise ValueError('Candidate case identity differs')
            if (p['candidate_id'], p['law_id'], p['cell_id'], p['actor'], p['duration_s'],
                p['rate_hz'], p['road_source'], p['comparison_variable']) != (
                ident, 'NRS-484B-283-1b', 'C230222', 'pedestrian', 12, 20,
                'native/road.xodr', 'pedestrian_departure_s'):
                raise ValueError('Candidate frozen contract differs')
            if e['pedestrian_departure_s'] != expected_start:
                raise ValueError('Controlled departure differs')
            if p['status'] != 'unselected_cpu_construction_plan_no_native_proof' or any(
                p[key] for key in ('actual_driver_yield_measured', 'impossibility_to_yield_proven')):
                raise ValueError('Candidate incorrectly claims readiness')
            if p['trigger']['physical_observation'] is not None:
                raise ValueError('Unobserved physical trigger claimed')
            plans[ident] = p
        primary = plans['primary']['engineering']
        for ident in IDS[1:]:
            current = plans[ident]['engineering']
            if {key: current[key] for key in FIXED} != {key: primary[key] for key in FIXED}:
                raise ValueError('Candidate changed fixed vehicle or capture condition')
        expected_changes = {'fallback1': {'pedestrian_spawn_x_m', 'pedestrian_pre_roll_s'},
                            'fallback2': {'pedestrian_control'},
                            'fallback3': {'camera_distance_m'}}
        for ident, expected in expected_changes.items():
            actual = {key for key, value in plans[ident]['engineering'].items()
                      if value != primary[key]}
            if actual != expected or plans[ident]['trigger']['threshold'] is None:
                raise ValueError('Fallback knobs or measured-trigger threshold differ')
        all_plans[suffix] = plans
    for ident in IDS:
        a = all_plans['probe_1'][ident]
        b = all_plans['probe_2'][ident]
        if {key: value for key, value in a['engineering'].items()
            if key != 'pedestrian_departure_s'} != {key: value for key, value in b['engineering'].items()
            if key != 'pedestrian_departure_s'}:
            raise ValueError('Controlled pair changes more than pedestrian departure')
    summary = json.loads((HERE / 'curb-engineering-summary.json').read_text())
    if summary['unselected_candidate_plans'] != 8 or summary['selected_cases'] != 0 or summary['physically_measured_triggers'] != 0:
        raise ValueError('Engineering summary claims unsupported progress')
    if summary['synthetic_trigger_metrics']['synthetic_spawn_clearance_m'] != .88:
        raise ValueError('Synthetic source clearance differs')
    runner = json.loads((HERE / 'curb-runner-summary.json').read_text())
    if len(runner['records']) != 8 or runner['native_attempts'] or runner['accepted_recordings']:
        raise ValueError('Runner CPU proof claims unsupported execution')
    for record in runner['records']:
        suffix = record['case_id'].rsplit('__', 1)[-1]
        expected = .5 if suffix == 'probe_1' else 3.5
        policy = record['driver_policy_cpu_probe']
        if (policy['departure_observed_s'] != expected or
            abs(policy['brake_command_onset_s'] - (expected+.8)) > 1e-9 or
            policy['physical_braking_measured']):
            raise ValueError('Runner shared driver policy differs')
    return {'independent_audit': 'pass', 'controlled_pairs': 4,
            'unselected_candidate_plans': 8, 'driver_policy_cpu_probes': 8,
            'physical_triggers_measured': 0}


if __name__ == '__main__':
    print(json.dumps(audit()))
