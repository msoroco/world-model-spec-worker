"""Write exact-law semantic stage proposals for the selected crosswalk cases."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.name
PROPOSALS = FOLDER / 'proposals'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    original = json.loads((FOLDER.parents[1] / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    law_id, cell_id, actor = (original[key] for key in ('law_id', 'cell_id', 'actor'))
    law = original['law']['text']
    template_id = law_id + '@' + actor
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': law,
            'applies_to': [actor], 'relevance_type': 'specific_match',
            'confidence': 'high',
            'notes': 'Exact crosswalk stopping, standing and parking prohibition for this driver.'}],
        'borderline_excluded': []}
    write(PROPOSALS / 'relevance.json', relevance)
    write(PROPOSALS / 'relevance_batch.json', relevance)
    template = {'template_id': template_id, 'law_id': law_id,
        'actor': actor, 'status': 'draft', 'quote': law,
        'structure': {'law_id': law_id,
            'activation': {'condition': 'Vehicle stops, stands or parks on a source-reviewed crosswalk.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Do not stop, stand or park on a crosswalk unless an exact source exception applies.',
                           'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [
                {'trigger': 'Necessary to avoid conflict with other traffic',
                 'effect': 'The prohibition has an exception when necessity is established from original traffic evidence.',
                 'replacement_obligation': 'Retain the original traffic evidence for independent review.',
                 'source_clause': 'except when necessary to avoid conflict with other traffic'},
                {'trigger': 'In compliance with law',
                 'effect': 'The prohibition has an exception when another law actually requires the activity.',
                 'replacement_obligation': 'Retain the source authority for independent review.',
                 'source_clause': 'in compliance with law'},
                {'trigger': 'Directions of a police officer',
                 'effect': 'The prohibition has an exception when an actual police direction applies.',
                 'replacement_obligation': 'Retain original officer direction evidence for review.',
                 'source_clause': 'the directions of a police officer'},
                {'trigger': 'Official traffic-control device',
                 'effect': 'The prohibition has an exception when an official device direction applies.',
                 'replacement_obligation': 'Retain original device authority and indication evidence for review.',
                 'source_clause': 'official traffic-control device'}],
            'timing': {'description': 'Observe the complete interval of stopping, standing or parking on the crosswalk.',
                       'numeric_conditions': []},
            'judgment_calls_needed': []},
        'parameter_refs': [
            {'name': 'target_variant', 'kind': 'controller', 'range_or_domain': 'clear or occupy requested crosswalk target'},
            {'name': 'activity_mode', 'kind': 'controller', 'range_or_domain': 'stop, stand or park requested mode'},
            {'name': 'exception_context_request', 'kind': 'controller', 'range_or_domain': 'traffic, other-law, officer or device present/absent request'},
            {'name': 'observed_crosswalk_state', 'kind': 'subject_behavior', 'range_or_domain': 'original footprint, speed and source context or unknown'}]}
    write(PROPOSALS / 'template.json', template)
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': [], 'law_refs': [{'template_id': template_id,
            'binding_kind': 'direct'}], 'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[law_id])
            for item in template['parameter_refs']]}
    write(PROPOSALS / 'bindings.json', bindings)
    proposal = json.loads((PROPOSALS / 'cases.json').read_text())
    description = proposal['cases'][0]['recording_description']
    baseline_assignments = {'target_variant': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'activity_mode': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'exception_context_request': {'kind': 'controller', 'value': None, 'unit': 'category'},
        'observed_crosswalk_state': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'}}
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'cell_id': cell_id, 'actor': actor,
        'rationale': 'Unselected common crosswalk and driver context.',
        'variable_assignments': baseline_assignments,
        'recording_description': description, 'unresolved_judgment_calls': []}
    selected = []
    for case in (c for c in proposal['cases'] if c.get('target_type') != 'baseline'):
        suffix = case['case_id'].removeprefix(ASSIGNMENT + '__')
        bundle = json.loads((FOLDER / 'native' / 'bundles' / suffix / 'construction.json').read_text())
        config = json.loads(next(f['content'] for f in bundle['files'] if f['path'] == 'config.json'))
        if suffix.startswith('witness'):
            pair, changed = 'park_occupancy', 'target_variant'
            target_type = 'compliant_attempt' if suffix.endswith('_1') else 'violating_attempt'
        elif suffix.startswith('stop'):
            pair, changed, target_type = 'stop_occupancy', 'target_variant', 'boundary_probe'
        elif suffix.startswith('stand'):
            pair, changed, target_type = 'stand_occupancy', 'target_variant', 'boundary_probe'
        else:
            pair = 'exception_' + suffix.split('_')[1]
            changed, target_type = 'exception_context_request', 'boundary_probe'
        assignments = json.loads(json.dumps(baseline_assignments))
        assignments['target_variant']['value'] = config['target_variant']
        assignments['activity_mode']['value'] = config['branch']
        assignments['exception_context_request']['value'] = suffix if suffix.startswith('exception') else 'none'
        differences = ['target_variant', 'exception_context_request'] if suffix.startswith('exception') else [changed]
        case.update(target_type=target_type, cell_id=cell_id, actor=actor,
            paired_probe_id=pair, deliberate_differences=differences,
            probe={'primary_variable': changed,
                   'comparison_or_standard': 'same crosswalk and source law with paired target request',
                   'target_value_or_branch': assignments[changed]['value']},
            variable_assignments=assignments)
        selected.append(case)
    proposal['cases'] = [baseline] + selected
    proposal['sweep_specs'] = []
    proposal['sweeps_expanded'] = True
    write(PROPOSALS / 'cases.json', proposal)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
        'stages': {key: {'path': 'proposals/' + key + '.json',
                         'sha256': sha(PROPOSALS / (key + '.json'))}
                   for key in ('relevance_batch', 'relevance', 'template', 'bindings', 'cases')}}
    index['stages']['judgment_observables'] = []
    write(PROPOSALS / 'semantic-index.json', index)


if __name__ == '__main__':
    build()
