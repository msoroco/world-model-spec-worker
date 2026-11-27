"""Build canonical planning cases without changing the two delivery candidates."""
from copy import deepcopy
import json
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[1]
REPO = next(parent for parent in PACKAGE.parents if (parent / 'batch.json').is_file())
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


def read(path):
    return json.loads(path.read_text())


proposal = PACKAGE / 'proposals'
existing = read(proposal / 'delivery_candidates.json')
binding = read(proposal / 'bindings.json')
template = read(proposal / 'template.json')
for index, judgment in enumerate(template['structure']['judgment_calls_needed']):
    judgment['observable_requirements'] = read(proposal / f'judgment_observables_{index}.json')['observable_requirements']

base = deepcopy(existing['cases'][0])
base['variable_assignments']['oncoming_centre_distance_ft'] = {'kind': 'subject_behavior', 'value': None}
base['target_law_id'] = None
base['target_type'] = 'baseline'
base['case_id'] = f"{PACKAGE.name}__baseline"
base['rationale'] = 'Shared opposed-vehicle shoulder and beam request reference; no legal conclusion.'
base['unresolved_judgment_calls'] = [j['phrase'] for j in template['structure']['judgment_calls_needed']]
base.pop('sweep_measurements', None)
cases = [base]
for original, policy in zip(existing['cases'], ('dim_within_500', 'retain_high')):
    case = deepcopy(original)
    case['variable_assignments']['oncoming_centre_distance_ft'] = {'kind': 'subject_behavior', 'value': None}
    case['target_type'] = 'judgment_sweep'
    case['paired_probe_id'] = f'{PACKAGE.name}__beam_contrast'
    case['deliberate_differences'] = ['beam_request_policy']
    case['rationale'] = 'Physical low/high beam-request contrast with all legal judgment phrases unresolved.'
    case['probe'] = {'primary_variable': 'beam_request_policy',
                     'comparison_or_standard': 'fixed original road and trajectory beam-request contrast',
                     'target_value_or_branch': policy}
    case['unresolved_judgment_calls'] = base['unresolved_judgment_calls']
    cases.append(case)
for branch, value in [('below', 499), ('at', 500), ('above', 501)]:
    case = deepcopy(base)
    case.update(case_id=f'{PACKAGE.name}__distance_{branch}_500ft', target_law_id=template['law_id'],
                target_type='boundary_probe', paired_probe_id=f'{PACKAGE.name}__distance_500ft',
                deliberate_differences=['oncoming_centre_distance_ft'],
                rationale=f'Physical separation target {value} ft relative to exact 500 ft statutory boundary; measured original distance controls any later interpretation.',
                probe={'primary_variable': 'oncoming_centre_distance_ft',
                       'comparison_or_standard': 'exact statutory 500 ft onset',
                       'target_value_or_branch': branch,
                       'threshold_ref': 'obligation.numeric_conditions[0]',
                       'operator': '<=', 'unit': 'ft', 'test_value': value},
                epsilon_used={'value': 1, 'unit': 'ft', 'rationale': 'Planning grid spacing only; exact at-boundary observation cannot be guaranteed by this controller.'})
    case['variable_assignments']['beam_request_policy'] = {'kind': 'controller', 'value': 'dim_within_500'}
    cases.append(case)

for branch, policy in [('visibility_dim', 'dim_within_500'),
                       ('visibility_high', 'retain_high')]:
    case = deepcopy(base)
    case.update(case_id=f'{PACKAGE.name}__{branch}', target_law_id=template['law_id'],
                target_type='judgment_sweep', paired_probe_id=f'{PACKAGE.name}__visibility_1000ft',
                deliberate_differences=['beam_request_policy'],
                rationale='Controlled fog and an authored 1000-foot oncoming vehicle target; original actor range and decoded discernibility review remain decisive.',
                probe={'primary_variable': 'beam_request_policy',
                       'comparison_or_standard': 'fixed original 1000-foot target, fog request, road and trajectory',
                       'target_value_or_branch': policy})
    case['variable_assignments']['beam_request_policy'] = {'kind': 'controller', 'value': policy}
    case['probe']['fixed_visibility_request'] = 'controlled_fog_1000ft_target'
    case['unresolved_judgment_calls'] = base['unresolved_judgment_calls']
    cases.append(case)

for branch, policy in [('device_dim', 'dim_within_500'),
                       ('device_high', 'retain_high')]:
    case = deepcopy(base)
    case.update(case_id=f'{PACKAGE.name}__{branch}', target_law_id=template['law_id'],
                target_type='judgment_sweep', paired_probe_id=f'{PACKAGE.name}__device_directive_beam',
                deliberate_differences=['beam_request_policy'],
                rationale='Same adjacent shoulder and opposed vehicle with authored lamp-use signal; original device authority, applicability and decoded visibility remain independent review.',
                probe={'primary_variable': 'beam_request_policy',
                       'comparison_or_standard': 'fixed original road, oncoming trajectory, authored signal readback and time',
                       'target_value_or_branch': policy,
                       'fixed_device_request': 'authored_lamp_use_instruction_official_status_unverified'})
    case['variable_assignments']['beam_request_policy'] = {'kind': 'controller', 'value': policy}
    case['unresolved_judgment_calls'] = base['unresolved_judgment_calls']
    cases.append(case)

specs = []
for index, judgment in enumerate(template['structure']['judgment_calls_needed']):
    specs.append({'sweep_id': f'{PACKAGE.name}__judgment_{index}', 'target_law_id': template['law_id'],
                  'judgment_refs': [{'phrase': judgment['phrase'], 'note': judgment['note']}],
                  'status': 'incomplete', 'rationale': 'Original physical observations and feasible setpoint grid are not yet independently established.',
                  'missing_inputs': [
                      'Verified original CARLA optical or equipment observation for the exact phrase',
                      'Supported canonical controller or world setup axis with feasible range and spacing',
                      'Measured source-backed recording and landmark evidence']})

result = {'cell_id': existing['cell_id'], 'actor': existing['actor'], 'status': 'draft',
          'sweeps_expanded': True, 'sweep_specs': specs, 'cases': cases}
request = {'cell': read(REPO / 'inputs' / PACKAGE.name / 'assignment.json')['cell'],
           'actor': existing['actor']}
stages.validate('cases', result, {'request': request, 'dependencies': [binding], 'templates': [template]})
destination = proposal / 'canonical_cases.json'
destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
(proposal / 'cases.json').write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
print(f'PASS: canonical baseline, two beam contrast cases, linked 499/500/501 ft probes, two visibility cases, two device cases, and three explicit incomplete judgment sweep plans; {destination.relative_to(PACKAGE)}')
