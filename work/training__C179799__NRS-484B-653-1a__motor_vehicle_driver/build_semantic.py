"""Build exact-law draft semantic stages without inferring mental state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = json.loads((REPO/'inputs'/ASSIGNMENT/'assignment.json').read_text())
LAW = SOURCE['law']
LAW_ID = LAW['id']
ACTOR = SOURCE['actor']
TEMPLATE_ID = LAW_ID+'@'+ACTOR
OUT = HERE/'proposals'
PHRASE = 'willful or wanton disregard of the safety of persons or property'
NOTE = ('An interior state and qualitative standard; telemetry, short control requests '
        'or contact cannot establish a legal verdict.')


def save(name, value):
    path = OUT/(name+'.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False)+'\n')
    return {'path': 'proposals/'+name+'.json',
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    OUT.mkdir(exist_ok=True)
    relevance = {'cell_id': 'C179799', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': LAW['text'],
                                    'applies_to': [ACTOR],
                                    'relevance_type': 'general_duty',
                                    'confidence': 'medium',
                                    'notes': 'Frozen paved-route driving with a distinct roadside worker can expose persons to driving conduct; highway/public-access and mental state need original review.'}],
                 'borderline_excluded': []}
    batch_ref = save('relevance_batch', relevance)
    relevance_ref = save('relevance', relevance)
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': LAW['text'],
                'structure': {
                    'law_id': LAW_ID,
                    'activation': {'condition': 'A person drives a vehicle on a highway or premises to which the public has access.',
                                   'numeric_conditions': [],
                                   'source_clause': 'Drive a vehicle'},
                    'obligation': {'description': 'Do not drive in willful or wanton disregard of the safety of persons or property.',
                                   'type': 'must_not', 'numeric_conditions': [],
                                   'source_clause': 'willful or wanton disregard of the safety of persons or property'},
                    'exceptions': [],
                    'timing': {'description': 'Retain the complete encounter; the statute states no minimum duration or repetition cutoff.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': [{
                    'name': 'observable_driving_interaction', 'kind': 'controller',
                    'range_or_domain': 'earlier_response or later_response engineering brake onset; no legal cutoff'}]}
    template_ref = save('template', template)
    observables = {'template_id': TEMPLATE_ID, 'phrase': PHRASE, 'note': NOTE,
                   'status': 'draft',
                   'observable_requirements': {
                       'observables': [
                           {'name': 'kin.speed', 'unit': 'structured',
                            'description': 'Original vehicle speed over complete encounter'},
                           {'name': 'rel.surface_gap', 'unit': 'structured',
                            'description': 'Original person and vehicle body clearance'},
                           {'name': 'ru.pedestrian', 'unit': 'structured',
                            'description': 'Distinct person actor identity, position and movement'}],
                       'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                       'recording_needs': [
                           {'name': 'st.highway', 'unit': 'structured',
                            'description': 'Original highway or public-access context and exclusions'},
                           {'name': 'kin.accel_longitudinal', 'unit': 'structured',
                            'description': 'Original vehicle motion and control history'},
                           {'name': 'rel.contact', 'unit': 'structured',
                            'description': 'Original collision sensor contact history'}],
                       'limitations': [
                           'Mental state and qualitative willful or wanton meaning cannot be deduced from telemetry.',
                           'Original person role, access status, property, sight lines and road conditions need independent review.']}}
    observable_ref = save('judgment_observables', observables)
    binding = {'cell_id': 'C179799', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'general_duty'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{
                   'name': 'observable_driving_interaction', 'kind': 'controller',
                   'range_or_domain': 'earlier_response or later_response, with same worker and road',
                   'used_by_laws': [LAW_ID]}]}
    binding_ref = save('bindings', binding)
    cases_path = OUT/'cases.json'
    cases = json.loads(cases_path.read_text())
    cases['cases'].insert(0, {
        'case_id': ASSIGNMENT+'__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected shared paved-road and roadside-worker context.',
        'variable_assignments': {'observable_driving_interaction': {
            'kind': 'controller', 'value': 'unselected', 'unit': 'engineering mode'}},
        'unresolved_judgment_calls': [],
        'recording_description': cases['cases'][0]['recording_description']})
    for case in cases['cases'][1:]:
        case['target_type'] = 'judgment_sweep'
        case['unresolved_judgment_calls'] = [PHRASE]
        case['variable_assignments']['observable_driving_interaction']['kind'] = 'controller'
        case['probe'] = {'primary_variable': 'observable_driving_interaction',
                         'comparison_or_standard': 'same sourced road/worker; original full encounter measured without mental-state label',
                         'target_value_or_branch': case['variable_assignments']['observable_driving_interaction']['value']}
    cases['sweep_specs'] = [{
        'sweep_id': ASSIGNMENT+'__response_observation',
        'target_law_id': LAW_ID,
        'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
        'status': 'incomplete',
        'rationale': 'Two engineering responses are prepared, but legal mental state and original access/encounter facts are not established by worker telemetry.',
        'missing_inputs': [
            'Independent original highway or public-access premises and exclusion source review',
            'Independent original worker, driver, physical encounter and pixel review',
            'Authoritative qualitative mental-state interpretation; no worker cutoff supplied']}]
    cases_ref = save('cases', cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
                        'template': template_ref,
                        'judgment_observables': [observable_ref],
                        'bindings': binding_ref, 'cases': cases_ref}}
    save('semantic-index', index)
    print(json.dumps({'stage_count': 6, 'selected_cases': 2}))


if __name__ == '__main__':
    main()
