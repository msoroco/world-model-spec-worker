"""Author the six source-hashed canonical proposal stages for the arrow clause."""
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
P = HERE / 'proposals'
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT', str(ROOT / '.runtime-work/c110919-3a-owner'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate as validate_semantic


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    prior = json.loads((P / 'cases.json').read_text())
    recording = prior['cases'][0]['recording_description']
    law_id, actor, cell_id = (assignment[key] for key in ('law_id', 'actor', 'cell_id'))
    quote = assignment['law']['text']
    template_id = f'{law_id}@{actor}'
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'Circular green with right arrow at the frozen signalized right-turn cell; original signal and lawful-user facts remain unobserved.'}],
                 'borderline_excluded': []}
    write(P / 'relevance_batch.json', relevance)
    write(P / 'relevance.json', relevance)
    phrase = 'lawfully within'
    note = 'Legal status of pedestrians and traffic requires independent source review and rule composition.'
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'activation': {'condition': 'Facing circular green and illuminated right-turn arrow',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must',
                                   'description': 'Right-turning traffic yields to pedestrians lawfully in the adjacent crosswalk and other traffic lawfully using the intersection when the signal is exhibited.',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Throughout the illuminated arrow and before entry into an occupied conflict area; opposing traffic is advised to face steady red.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}]},
                'parameter_refs': []}
    write(P / 'template.json', template)
    requirements = {'observables': [
                        {'name': 'dev.traffic_signal', 'unit': 'structured',
                         'description': 'Original facing signal and opposing red state with head IDs and arrow pixels.'},
                        {'name': 'st.crosswalk', 'unit': 'structured',
                         'description': 'Original adjacent-crosswalk geometry and pedestrian occupancy.'},
                        {'name': 'drv.yields_to', 'unit': 'structured',
                         'description': 'Frame-joined ego body, conflict entry and pedestrian/traffic clearance.'}],
                    'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                    'recording_needs': [{'name': 'dev.traffic_signal', 'unit': 'structured',
                                         'description': 'Full signal and arrow-state source sequence.'}],
                    'limitations': ['Synthetic source states cannot prove physical arrow glyph, facing direction or lawful-user status.']}
    write(P / 'judgment_observables_lawful.json',
          {'template_id': template_id, 'phrase': phrase, 'note': note,
           'status': 'draft', 'observable_requirements': requirements})
    binding = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
               'established_contexts': [{'name': 'right_turn_signalized_intersection',
                                         'source': 'frozen cell layout, maneuver and control'}],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'requested_turn_entry_frame', 'kind': 'controller',
                    'range_or_domain': 'authored frame 145 or 181; original body entry measured separately',
                    'used_by_laws': [law_id]},
                   {'name': 'pedestrian_yield_observation', 'kind': 'subject_behavior',
                    'range_or_domain': 'original source-joined pedestrian conflict and ego body',
                    'used_by_laws': [law_id]}]}
    write(P / 'bindings.json', binding)
    cases = []
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        frame = 181 if witness == 'witness_1' else 145
        cases.append({'case_id': entry['case_id'], 'target_law_id': law_id,
                      'target_type': 'boundary_probe',
                      'rationale': 'Same-map right-arrow request with a different authored turn-entry frame; original yielded behavior and legal status remain unobserved.',
                      'paired_probe_id': 'right_arrow_pedestrian_yield_contrast',
                      'deliberate_differences': ['requested_turn_entry_frame'],
                      'probe': {'primary_variable': 'requested_turn_entry_frame',
                                'comparison_or_standard': 'frame-joined pedestrian conflict interval, not a legal threshold',
                                'target_value_or_branch': frame},
                      'variable_assignments': {
                          'requested_turn_entry_frame': {'kind': 'controller', 'value': frame},
                          'pedestrian_yield_observation': {'kind': 'subject_behavior', 'value': None}},
                      'recording_description': recording,
                      'unresolved_judgment_calls': [phrase]})
    spec = {'sweep_id': 'c110919-lawfully-within-source-pending',
            'target_law_id': law_id, 'judgment_refs': [{'phrase': phrase, 'note': note}],
            'rationale': 'Original lawful status requires independent rule composition and source review.',
            'status': 'incomplete',
            'missing_inputs': ['original pedestrian and other-traffic right-of-way source context',
                               'original arrow pixels and independent physical review']}
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Shared right-arrow intersection context; no baseline recording selected.',
                'variable_assignments': {
                    'requested_turn_entry_frame': {'kind': 'controller', 'value': 181},
                    'pedestrian_yield_observation': {'kind': 'subject_behavior', 'value': None}},
                'recording_description': recording,
                'unresolved_judgment_calls': [phrase]}
    canonical = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'cases': [baseline, *cases], 'sweep_specs': [spec], 'sweeps_expanded': True}
    write(P / 'canonical-cases.json', canonical)
    write(P / 'cases.json', {'format': 'worker-draft-proposals-v1',
                             'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                             'sweep_specs': [], 'sweeps_expanded': True, 'cases': cases})
    stages = {name: {'path': f'proposals/{name}.json', 'sha256': sha(P / f'{name}.json')}
              for name in ('relevance_batch', 'relevance', 'template', 'bindings')}
    stages['cases'] = {'path': 'proposals/canonical-cases.json',
                       'sha256': sha(P / 'canonical-cases.json')}
    stages['judgment_observables'] = [{'path': 'proposals/judgment_observables_lawful.json',
                                       'sha256': sha(P / 'judgment_observables_lawful.json')}]
    write(P / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                      'assignment_id': HERE.name, 'stages': stages})
    print(json.dumps(validate_semantic(HERE, assignment, manifest)))


if __name__ == '__main__':
    build()
