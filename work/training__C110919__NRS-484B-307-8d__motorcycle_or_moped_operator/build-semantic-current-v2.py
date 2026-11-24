"""Bind the exact motorcycle source clause to draft CPU stage proposals."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = HERE / 'proposals'
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from batch_pipeline import stages
from worker_exchange.semantic_delivery import validate as validate_semantic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    original_proposal = json.loads((P / 'cases.json').read_text())
    recording = original_proposal['cases'][0]['recording_description']
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    quote = assignment['law']['text']
    template_id = f'{law_id}@{actor}'
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Frozen right-turn traffic-light cell and motorcycle actor match the clause; physical conditions remain to be observed.'}],
                 'borderline_excluded': []}
    write(P / 'relevance_batch.json', relevance)
    write(P / 'relevance.json', relevance)
    phrase = 'signal failed to detect the presence'
    note = 'Physical malfunction or nonresponse cause requires original signal and detector evidence.'
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'condition': 'steady red after a motorcycle stop',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must',
                                   'description': 'Wait for two complete cycles before the permitted right turn, with no prohibiting device and yield to directed traffic and pedestrians.',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'after complete cycles and before entering the right turn',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': []}
    write(P / 'template.json', template)
    requirements = {'observables': [
                        {'name': 'dev.traffic_signal', 'unit': 'structured',
                         'description': 'Original signal transitions and held red readback.'},
                        {'name': 'motorcycle_detector_request', 'unit': 'structured',
                         'description': 'Original detector request and response, with authored command separate.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [{'name': 'dev.traffic_signal', 'unit': 'structured',
                                         'description': 'Frame-joined signal state and cycle history.'}],
                    'limitations': ['Synthetic held-red command and cycle count do not establish physical detector nonresponse or legal cause.']}
    judgment = {'template_id': template_id, 'phrase': phrase, 'note': note,
                'status': 'draft', 'observable_requirements': requirements}
    write(P / 'judgment_observables_detector.json', judgment)
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'right_turn_signalized_intersection',
                                         'source': 'frozen cell layout, maneuver, and control'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_wait_cycles', 'kind': 'controller',
                    'range_or_domain': 'one or two authored complete signal cycles; measured separately',
                    'used_by_laws': [law_id]},
                   {'name': 'detector_request_mode', 'kind': 'controller',
                    'range_or_domain': 'authored withhold request; actual response unverified',
                    'used_by_laws': [law_id]},
                   {'name': 'motorcycle_body_history', 'kind': 'subject_behavior',
                    'range_or_domain': 'original Native full body path',
                    'used_by_laws': [law_id]}]}
    write(P / 'bindings.json', binding)
    base = {'requested_wait_cycles': {'kind': 'controller', 'value': 2},
            'detector_request_mode': {'kind': 'controller', 'value': 'withhold_request'},
            'motorcycle_body_history': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared authored intersection context; no baseline recording selected.',
                'variable_assignments': base, 'recording_description': recording,
                'unresolved_judgment_calls': [phrase]}
    cases = [baseline]
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        count = 2 if condition == 'condition_a' else 1
        assignments = json.loads(json.dumps(base))
        assignments['requested_wait_cycles']['value'] = count
        cases.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Same-map synthetic cycle contrast; original Native cause and legal characterization unresolved.',
                      'paired_probe_id': 'motorcycle_right_turn_two_cycle_contrast',
                      'deliberate_differences': ['requested_wait_cycles'],
                      'probe': {'primary_variable': 'requested_wait_cycles',
                                'comparison_or_standard': 'source-bound one versus two complete cycles, without a legal label',
                                'target_value_or_branch': count},
                      'variable_assignments': assignments,
                      'recording_description': recording,
                      'unresolved_judgment_calls': [phrase]})
    spec = {'sweep_id': 'c110919-detector-cause-pending', 'target_law_id': law_id,
            'judgment_refs': [{'phrase': phrase, 'note': note}],
            'rationale': 'Actual nonresponse cause needs independent signal/detector observation.',
            'status': 'incomplete',
            'missing_inputs': ['original Native detector request and response readback',
                               'physical signal phase and independent pixel review']}
    canonical = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'cases': cases, 'sweep_specs': [spec], 'sweeps_expanded': True}
    write(P / 'canonical-cases.json', canonical)
    proposal = {'format': 'worker-draft-proposals-v1', 'cell_id': cell_id,
                'actor': actor, 'status': 'draft', 'sweep_specs': [],
                'sweeps_expanded': True, 'cases': cases[1:]}
    write(P / 'cases.json', proposal)
    stages_map = {name: {'path': f'proposals/{name}.json', 'sha256': sha(P / f'{name}.json')}
                  for name in ('relevance_batch', 'relevance', 'template', 'bindings')}
    stages_map['cases'] = {'path': 'proposals/canonical-cases.json',
                           'sha256': sha(P / 'canonical-cases.json')}
    stages_map['judgment_observables'] = [
        {'path': 'proposals/judgment_observables_detector.json',
         'sha256': sha(P / 'judgment_observables_detector.json')}]
    write(P / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                      'assignment_id': HERE.name, 'stages': stages_map})
    print(json.dumps(validate_semantic(HERE, assignment, manifest)))


if __name__ == '__main__':
    build()
