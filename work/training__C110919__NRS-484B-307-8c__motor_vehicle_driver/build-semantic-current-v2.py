"""Bind the exact 8c right-turn clause to canonical draft stage proposals."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = HERE / 'proposals'
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate as validate_semantic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    quote = assignment['law']['text']
    template_id = f'{law_id}@{actor}'
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote, 'applies_to': [actor],
                                    'relevance_type': 'specific_match', 'confidence': 'medium',
                                    'notes': 'The frozen traffic-light right-turn cell matches the right-turn alternative; original physical prerequisites remain unobserved.'}],
                 'borderline_excluded': []}
    write(P / 'relevance_batch.json', relevance)
    write(P / 'relevance.json', relevance)
    phrase = 'must yield the right-of-way to pedestrians and other traffic proceeding as directed'
    note = 'Original directed traffic and pedestrian conflict occupancy require independent physical review.'
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor, 'status': 'draft',
                'quote': quote, 'structure': {
                    'activation': {'condition': 'steady red alone, complete stop, extreme-right lane and two-way or rightward one-way destination',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must', 'description': 'Yield during the right turn to pedestrians and traffic proceeding as directed.',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'full stop before entry and yielding throughout the right turn', 'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': []}
    write(P / 'template.json', template)
    requirements = {'observables': [
                        {'name': 'dev.traffic_signal', 'unit': 'structured', 'description': 'Original governing red signal and directed traffic control.'},
                        {'name': 'drv.yields_to', 'unit': 'structured', 'description': 'Original joined ego/pedestrian/directed-traffic body conflict and clearance.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [{'name': 'drv.yields_to', 'unit': 'structured',
                                         'description': 'Frame-joined conflict and right-turn source review.'}],
                    'limitations': ['Synthetic actor trajectories and authored yield commands do not establish actual Native yield or legal permission.']}
    write(P / 'judgment_observables_yield.json', {'template_id': template_id, 'phrase': phrase,
                                                   'note': note, 'status': 'draft',
                                                   'observable_requirements': requirements})
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'steady_red_two_way_right_turn',
                                         'source': 'frozen cell and authored map; Native readback pending'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_pre_turn_halt', 'kind': 'controller',
                    'range_or_domain': 'authored halt request versus rolling request; actual motion measured separately', 'used_by_laws': [law_id]},
                   {'name': 'governing_red_signal', 'kind': 'controller',
                    'range_or_domain': 'authored steady red with original readback required', 'used_by_laws': [law_id]},
                   {'name': 'pedestrian_and_directed_traffic_yield', 'kind': 'subject_behavior',
                    'range_or_domain': 'source-joined conflict and clearance, physical review pending',
                    'used_by_laws': [law_id]}]}
    write(P / 'bindings.json', binding)
    base = {'requested_pre_turn_halt': {'kind': 'controller', 'value': None},
            'governing_red_signal': {'kind': 'controller', 'value': 'steady_red'},
            'pedestrian_and_directed_traffic_yield': {'kind': 'subject_behavior', 'value': None}}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'rationale': 'Shared authored intersection; no baseline recording selected.',
                'variable_assignments': base,
                'recording_description': json.loads((HERE / manifest['cases'][0]['construction']).read_text())['recording_description'],
                'unresolved_judgment_calls': [phrase]}
    cases = [baseline]
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        halt = suffix == 'probe_a'
        assignments = json.loads(json.dumps(base))
        assignments['requested_pre_turn_halt']['value'] = halt
        recording = json.loads((HERE / entry['construction']).read_text())['recording_description']
        cases.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Same-map synthetic full-halt contrast; original Native motion and legal assessment unresolved.',
                      'paired_probe_id': 'steady_red_full_halt_contrast',
                      'deliberate_differences': ['requested_pre_turn_halt'],
                      'probe': {'primary_variable': 'requested_pre_turn_halt',
                                'comparison_or_standard': 'source-bound full halt versus rolling control without legal label',
                                'target_value_or_branch': halt},
                      'variable_assignments': assignments,
                      'recording_description': recording,
                      'unresolved_judgment_calls': [phrase]})
    canonical = {'cell_id': cell_id, 'actor': actor, 'status': 'draft', 'cases': cases,
                 'sweep_specs': [{'sweep_id': 'c110919-8c-yield-physical-pending', 'target_law_id': law_id,
                                  'judgment_refs': [{'phrase': phrase, 'note': note}],
                                  'rationale': 'Actual directed traffic and pedestrian yield need original Native review.',
                                  'status': 'incomplete',
                                  'missing_inputs': ['original Native body/signal/actor readback',
                                                     'independent source pixel review']}],
                 'sweeps_expanded': True}
    write(P / 'canonical-cases.json', canonical)
    write(P / 'cases.json', {'format': 'worker-draft-proposals-v1', 'cell_id': cell_id,
                            'actor': actor, 'status': 'draft', 'sweep_specs': [],
                            'sweeps_expanded': True, 'cases': cases[1:]})
    stages = {name: {'path': f'proposals/{name}.json', 'sha256': sha(P / f'{name}.json')}
              for name in ('relevance_batch', 'relevance', 'template', 'bindings')}
    stages['cases'] = {'path': 'proposals/canonical-cases.json',
                       'sha256': sha(P / 'canonical-cases.json')}
    stages['judgment_observables'] = [{'path': 'proposals/judgment_observables_yield.json',
                                       'sha256': sha(P / 'judgment_observables_yield.json')}]
    write(P / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                      'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps(validate_semantic(HERE, assignment, manifest)))


if __name__ == '__main__':
    build()
