"""Bind all expanded judgment cases to the exact assignment plan."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    stage = json.loads((HERE / 'proposals/cases.json').read_text())
    sweeps = [case for case in stage['cases']
              if case['target_type'] == 'judgment_sweep']
    if len(sweeps) != 6:
        raise ValueError('Six exact canonical sweep cases required')
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    plan['cases'] = [case for case in plan['cases']
                     if case.get('target_type') != 'judgment_sweep']
    plan['comparisons'] = [comparison for comparison in plan['comparisons']
                           if not comparison['comparison_id'].endswith(('__judgment-1', '__judgment-2'))]
    for case in sweeps:
        axis, point = next(iter(case['sweep_point'].items()))
        plan['cases'].append({
            'case_id': case['case_id'], 'target_law_id': case['target_law_id'],
            'planning_status': 'physical_sweep_target_only_legal_judgment_unresolved',
            'target_type': 'judgment_sweep', 'comparison_variable': axis,
            'comparison_unit': 'm/s2' if 'acceleration' in axis else 'm',
            'requested_setting': point, 'recorded_value': None,
            'case_description': case['rationale'],
            'fixed_context': 'Hold cell, actor, four-camera 30-second recording, weather and noncompared settings fixed; source-check original Native route and response.',
            'source_topic_ids': ['text-0'], 'sweep_id': case['sweep_id'],
            'unresolved_judgment_calls': case['unresolved_judgment_calls']})
    for spec in stage['sweep_specs']:
        plan['comparisons'].append({
            'comparison_id': spec['sweep_id'], 'case_ids': spec['selection_order'],
            'deliberate_differences': [spec['axes'][0]['variable']],
            'fixed_conditions': ['cell', 'actor', 'law and context review rule',
                                 'weather', 'other controller settings',
                                 'camera and capture profile'],
            'status': 'planned_physical_sweep_original_response_unverified'})
    ids = [case['case_id'] for case in plan['cases']]
    if len(ids) != 8 or len(set(ids)) != 8:
        raise ValueError('Exact eight-case plan differs')
    write(plan_path, plan)
    config_path = HERE / 'config.json'
    config = json.loads(config_path.read_text())
    config['supported_case_ids'] = ids
    write(config_path, config)
    construction_path = HERE / 'construction.json'
    construction = json.loads(construction_path.read_text())
    for file in construction['files']:
        if file['path'] == 'config.json':
            file['content'] = config_path.read_text()
    write(construction_path, construction)
    print(json.dumps({'selected_plan_cases': len(ids), 'comparisons': len(plan['comparisons'])}))


if __name__ == '__main__':
    main()
