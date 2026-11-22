"""Expand feasible source-hashed judgment brackets into exact draft capture cases.

The requested values are physical targets. They are not accepted observations or
legal cutoffs; actual steady-window values must be reviewed after Native runs.
"""
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
PLAN = ROOT/'case-plan.json'
PROPOSAL = ROOT/'proposals/cases.json'
RANGES = ROOT/'judgment-probe-plan.json'
FIELD = {'along_route_body_gap': 'target_body_gap_m',
         'leader_speed': 'leader_target_speed_mps',
         'relative_speed': 'ego_target_speed_mps',
         'surrounding_vehicle_count': 'surrounding_vehicle_count',
         'native_precipitation_strength': 'precipitation_percent',
         'native_fog_density': 'fog_density_percent',
         'observed_tire_friction': 'tire_friction'}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def observed_target(setup, variable):
    if variable == 'relative_speed':
        return setup['ego_target_speed_mps']-setup['leader_target_speed_mps']
    return setup[FIELD[variable]]


def in_zone(value, row, zone):
    low, high = row['source_minimum'], row['source_maximum']
    return ((zone == 'below' and value < low) or
            (zone == 'inside' and low < value < high) or
            (zone == 'above' and value > high))


def main():
    plan = json.loads(PLAN.read_text())
    proposal = json.loads(PROPOSAL.read_text())
    ranges = json.loads(RANGES.read_text())
    plan['cases'] = [c for c in plan['cases'] if not c['case_id'].split('__')[-1].startswith('range_')]
    plan['comparisons'] = [c for c in plan['comparisons'] if not c['comparison_id'].startswith('range_')]
    proposal['cases'] = [c for c in proposal['cases'] if not c['case_id'].split('__')[-1].startswith('range_')]
    base = plan['cases'][0]
    base_proposal = proposal['cases'][1]
    for case in plan['cases']:
        setup = case['world_setup']
        setup.setdefault('fog_density_percent', 0)
        setup.setdefault('tire_friction', 2.0)
        suffix = case['case_id'].removeprefix(ASSIGNMENT+'__')
        scene_path = ROOT/'scene.json' if suffix == 'following_base_probe' else ROOT/'cases'/suffix/'scene.json'
        scene = json.loads(scene_path.read_text())
        scene.update(setup)
        scene['lane_change_start_s'] = 21
        write(scene_path, scene)
    by_id = {c['case_id']: c for c in plan['cases']}
    for case in proposal['cases']:
        if case['target_type'] == 'baseline':
            setup = base['world_setup']
        else:
            setup = by_id[case['case_id']]['world_setup']
        for name in ('fog_density_percent', 'tire_friction'):
            case['variable_assignments'][name] = {
                'kind': 'world_setup', 'value': setup[name]}
    for row in ranges['ranges']:
        row['planned_case_ids'] = {}
        variable = row['variable']
        for zone, target in row['planning_targets'].items():
            if target is None:
                continue
            found = next((c for c in plan['cases'] if in_zone(
                observed_target(c['world_setup'], variable), row, zone)), None)
            if found is None:
                field = FIELD[variable]
                suffix = f"range_{variable}_{zone}_{row['range_index']}"
                case_id = ASSIGNMENT+'__'+suffix
                setup = copy.deepcopy(base['world_setup'])
                setup[field] = (setup['leader_target_speed_mps']+target
                                if variable == 'relative_speed' else target)
                if field == 'surrounding_vehicle_count':
                    setup[field] = int(target)
                case = copy.deepcopy(base)
                case['case_id'] = case_id
                case['world_setup'] = setup
                case['description'] = (f'Source range {row["range_index"]} '
                    f'{variable} {zone} physical target; no legal cutoff')
                plan['cases'].append(case)
                by_id[case_id] = case
                scene = dict(setup, case_id=case_id, law_id=plan['law_id'],
                             cell_id=plan['cell_id'], actor=plan['actor'],
                             lane_change_start_s=21)
                write(ROOT/'cases'/suffix/'scene.json', scene)
                projected = copy.deepcopy(base_proposal)
                projected['case_id'] = case_id
                projected['rationale'] = case['description']
                projected['variable_assignments'] = {
                    name: {'kind': base_proposal['variable_assignments'][name]['kind'],
                           'value': value} for name, value in setup.items()}
                projected['paired_probe_id'] = field
                projected['deliberate_differences'] = [field]
                projected['probe'] = {
                    'primary_variable': field,
                    'comparison_or_standard': 'Source-measured physical bracket; no legal cutoff',
                    'target_value_or_branch': target}
                proposal['cases'].append(projected)
                plan['comparisons'].append({
                    'comparison_id': suffix,
                    'case_ids': [base['case_id'], case_id],
                    'fixed_conditions': ['law', 'cell', 'actor',
                        'Native connected hill route', 'following lane and lane-change target',
                        'capture rate and duration', 'camera plan',
                        'non-varied controller settings'],
                    'deliberate_differences': [field],
                    'status': 'draft_needs_source_bound_audit'})
                found = case
            row['planned_case_ids'][zone] = [found['case_id']]
    for case in plan['cases']:
        case['judgment_refs'] = []
        case['sweep_measurements'] = []
    by_id = {c['case_id']: c for c in plan['cases']}
    for row in ranges['ranges']:
        for zone, ids in row['planned_case_ids'].items():
            for case_id in ids:
                case = by_id[case_id]
                if row['judgment_key'] not in case['judgment_refs']:
                    case['judgment_refs'].append(row['judgment_key'])
                case['sweep_measurements'].append({
                    'range_index': row['range_index'], 'judgment_key': row['judgment_key'],
                    'variable': row['variable'], 'unit': row['unit'],
                    'zone': zone,
                    'requested_target': observed_target(case['world_setup'], row['variable']),
                    'planning_target': row['planning_targets'][zone],
                    'source_ref': row['source_ref'], 'status': 'unmeasured'})
    for case in proposal['cases']:
        if case['target_type'] != 'baseline':
            source = by_id[case['case_id']]
            case['judgment_refs'] = source['judgment_refs']
            # The stage's sweep_measurements field triggers strict saved numeric
            # stream validation. These are planning targets until those streams
            # and actual Native samples exist; retain them under a draft key.
            case.pop('sweep_measurements', None)
            case['planned_sweep_measurements'] = source['sweep_measurements']
    case_ids = [c['case_id'] for c in plan['cases']]
    for disposition in plan['requirement_dispositions']:
        disposition['case_ids'] = case_ids
    proposal['sweeps_expanded'] = True
    write(PLAN, plan)
    write(PROPOSAL, proposal)
    write(RANGES, ranges)
    print(json.dumps({'exact_draft_cases': len(plan['cases']),
                      'comparisons': len(plan['comparisons']),
                      'unmeasured_source_ranges': len(ranges['ranges'])}))


if __name__ == '__main__':
    main()
