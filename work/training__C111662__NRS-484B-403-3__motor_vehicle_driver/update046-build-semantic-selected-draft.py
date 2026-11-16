"""Build a prospective semantic case chain with explicit district verification limits."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from batch_pipeline import stages  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    template = json.loads((HERE / 'proposals/template.json').read_text())
    observable = json.loads((HERE / 'proposals/judgment_observables_opening.json').read_text())
    template['structure']['judgment_calls_needed'][0]['observable_requirements'] = observable['observable_requirements']
    law_id = assignment['law_id']
    template_id = template['template_id']
    phrase = template['structure']['judgment_calls_needed'][0]['phrase']
    refs = [{'name': 'authored_business_frontage', 'kind': 'world_setup',
             'range_or_domain': 'prospective 328 ft business-use frontage in a 600 ft window; Native use and district boundaries pending',
             'used_by_laws': [law_id]},
            {'name': 'authored_exception_geometry', 'kind': 'world_setup',
             'range_or_domain': 'authored intersection or divided-highway crossing; generated geometry pending',
             'used_by_laws': [law_id]},
            {'name': 'requested_turn_center_x_m', 'kind': 'controller',
             'range_or_domain': 'authored -45 or 0 metre U-turn request, not observed crossing',
             'used_by_laws': [law_id]},
            {'name': 'ego_trajectory', 'kind': 'subject_behavior',
             'range_or_domain': 'original Native vehicle body and heading pending',
             'used_by_laws': [law_id]},
            {'name': 'camera_policy', 'kind': 'controller',
             'range_or_domain': 'four-view primary capture plan with tested physical fallbacks',
             'used_by_laws': [law_id]}]
    binding = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
               'established_contexts': [{'name': 'prospective_authored_business_frontage',
                                         'source': 'native/frontage-plan.json: authored 328.08 ft business-use request in 600 ft; actual business use and statutory district remain unverified'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [], 'variable_parameters': refs}
    request = {'cell': assignment['cell'], 'actor': assignment['actor'], 'template_ids': [template_id]}
    rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
    stages.validate('bindings', binding,
                    {'request': request, 'canonical_parameter_rules': rules, 'dependencies': [template]})
    binding_path = HERE / 'proposals/bindings-selected-draft.json'
    write(binding_path, binding)
    recording = json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description']
    names = {r['name']: r['kind'] for r in refs}

    def assignments(case, x):
        return {'authored_business_frontage': {'kind': 'world_setup', 'value': 'authored 328.08 ft prospective business frontage; actual district unverified'},
                'authored_exception_geometry': {'kind': 'world_setup', 'value':
                     'authored divided highway opening; appropriateness unverified' if case.startswith('divided_')
                     else 'authored intersection footprint; Native boundaries unverified'},
                'requested_turn_center_x_m': {'kind': 'controller', 'value': x, 'unit': 'm'},
                'ego_trajectory': {'kind': 'subject_behavior', 'value': None},
                'camera_policy': {'kind': 'controller', 'value': 'four_view_primary'}}

    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared prospective frontage and capture setup; no baseline recording selected.',
                'variable_assignments': assignments('reference', -45.0),
                'recording_description': recording, 'unresolved_judgment_calls': [phrase]}
    cases = [baseline]
    for suffix in ('reference', 'contrast', 'divided_reference', 'divided_opening'):
        case_id = HERE.name + '__' + suffix
        center = -45.0 if suffix in ('reference', 'divided_reference') else 0.0
        group = 'divided_opening_pair' if suffix.startswith('divided_') else 'intersection_pair'
        cases.append({'case_id': case_id, 'target_law_id': law_id,
                      'target_type': 'boundary_probe',
                      'rationale': 'Prospective authored U-turn crossing-location probe; statutory district, motion and exception status require original review.',
                      'variable_assignments': assignments(suffix, center),
                      'recording_description': recording,
                      'paired_probe_id': group,
                      'deliberate_differences': ['requested_turn_center_x_m'],
                      'probe': {'primary_variable': 'requested_turn_center_x_m',
                                'comparison_or_standard': 'observed vehicle-body crossing versus authored intersection or divided opening',
                                'target_value_or_branch': center},
                      'unresolved_judgment_calls': [phrase]})
    result = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
              'status': 'draft', 'cases': cases, 'sweep_specs': [{
                  'sweep_id': 'divided_opening_appropriateness_review', 'target_law_id': law_id,
                  'judgment_refs': template['structure']['judgment_calls_needed'],
                  'status': 'incomplete',
                  'rationale': 'Qualitative opening appropriateness and district applicability need original Native geometry and independent review.',
                  'missing_inputs': ['Original Native opening and vehicle body readback',
                                     'Reviewed business or industrial building use and district boundaries']}],
              'sweeps_expanded': True}
    for item in result['cases']:
        if set(item['variable_assignments']) != set(names):
            raise ValueError('Missing semantic variables')
    stages.validate('cases', result, {'request': {'cell': assignment['cell'], 'actor': assignment['actor']},
                                     'dependencies': [binding], 'templates': [template],
                                     'canonical_parameter_rules': rules,
                                     'judgment_completion_policy': {}})
    cases_path = HERE / 'proposals/cases-selected-draft.json'
    write(cases_path, result)
    print(json.dumps({'cases': len(cases), 'binding_sha256': sha(binding_path),
                      'cases_sha256': sha(cases_path),
                      'scope': 'prospective authored context; actual statutory district unverified'}))


if __name__ == '__main__':
    build()
