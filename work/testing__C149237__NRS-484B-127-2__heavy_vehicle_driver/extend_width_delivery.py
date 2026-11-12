"""Select the remaining exact 80-inch boundary cases without rewriting sealed eight-case bundles."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = HERE.name + '__'
SUFFIXES = ('ego_width_above_80in', 'lead_width_at_80in', 'lead_width_above_80in')
WIDTHS = {'ego_width_above_80in': ('ego', 2.1, 'above'),
          'lead_width_at_80in': ('lead', 2.032, 'at'),
          'lead_width_above_80in': ('lead', 2.1, 'above')}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE/'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan_path = HERE/'case-plan.json'
    plan = json.loads(plan_path.read_text())
    cases_path = HERE/'proposals/cases.json'
    cases = json.loads(cases_path.read_text())
    existing = {entry['case_id'] for entry in manifest['cases']}
    if any(PREFIX + suffix in existing for suffix in SUFFIXES):
        raise ValueError('Width delivery extension already selected; preserve existing proofs')
    template_manifest = next(e for e in manifest['cases'] if e['case_id'].endswith('__ego_width_at_80in'))
    template_construction = json.loads((HERE/template_manifest['construction']).read_text())
    template_case = next(c for c in cases['cases'] if c['case_id'].endswith('__ego_width_at_80in'))
    template_plan = next(c for c in plan['cases'] if c['case_id'].endswith('__ego_width_at_80in'))
    extension = (HERE/'width_boundary_extension.py').read_text()
    all_selected = [entry['case_id'] for entry in manifest['cases']] + [PREFIX+s for s in SUFFIXES]
    for suffix in SUFFIXES:
        case_id = PREFIX + suffix
        role, requested_width, side = WIDTHS[suffix]
        construction = deepcopy(template_construction)
        construction['case_id'] = case_id
        for file in construction['files']:
            if file['path'] == 'width_construction.py':
                file['content'] = extension
                file['source'] = str((HERE/'width_boundary_extension.py').relative_to(ROOT))
            elif file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['selected_case_id'] = case_id
                config['supported_case_ids'] = all_selected
                file['content'] = json.dumps(config, indent=2) + '\n'
        relative = f'gap-constructions/{suffix}.json'
        construction_path = HERE/relative
        save(construction_path, construction)
        manifest['cases'].append({
            'case_id': case_id, 'kind': 'delivery', 'construction': relative,
            'construction_sha256': sha(construction_path),
            'measurement_procedure': {'entrypoint': 'finalizer.py'},
            'measurement_contract': 'measurement-contract.json',
            'fixture_recipe': str((HERE/f'fixture-recipe-{suffix}.json').relative_to(ROOT)),
            'candidate_risk': {'status': 'physical',
                               'reason': 'No pinned Native truck asset may meet the exact measured 80-inch role category'},
            'candidates': []})
        planned = deepcopy(template_plan)
        planned.update(case_id=case_id,
                       purpose=f'{role} width {side} 80 inches; exact width-class boundary control')
        plan['cases'].append(planned)
        case = deepcopy(template_case)
        case['case_id'] = case_id
        case['rationale'] = f'Engineering {role} width {side} 80 inches; Native measurement and legal status unresolved.'
        case['paired_probe_id'] = 'truck_follow_' + ('ego_width' if role == 'ego' else 'lead_width')
        case['deliberate_differences'] = [f'requested_{role}_width_m']
        case['variable_assignments'][f'requested_{role}_width_m']['value'] = requested_width
        case['probe'] = {
            'primary_variable': f'{role}_overall_width',
            'comparison_or_standard': 'exact statutory boundary; physical value awaits Native readback',
            'target_value_or_branch': side,
            'threshold_ref': 'activation.numeric_conditions[0]' if role == 'ego' else 'activation.numeric_conditions[1]',
            'operator': '>=', 'unit': 'in', 'test_value': requested_width/.0254}
        cases['cases'].append(case)
    save(plan_path, plan)
    save(cases_path, cases)
    index_path = HERE/'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha(cases_path)
    save(index_path, index)
    manifest['status'] = 'partial_eleven_selected_width_coverage_unproved'
    save(manifest_path, manifest)


if __name__ == '__main__':
    main()
