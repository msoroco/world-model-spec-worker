"""Build source-faithful draft semantic proposals for exact selected cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / FOLDER.name / 'assignment.json').read_text())
PLAN = json.loads((FOLDER / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law_id']
CELL = ASSIGNMENT['cell_id']
ACTOR = ASSIGNMENT['actor']
QUOTE = ASSIGNMENT['law']['text']
TEMPLATE_ID = LAW + '@' + ACTOR
PROPOSALS = FOLDER / 'proposals'


def save(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def recording():
    names = ('actual_halt_activity', 'body_footprint_history',
             'official_device_instruction', 'effective_conditions',
             'exception_circumstances', 'capture_quality')
    channels = [{'name': name, 'unit': 'structured',
                 'method': 'source-sealed original Native frame and camera observation',
                 'time_window': 'all 900 original world ticks',
                 'reference_frame': 'original CARLA world frame',
                 'sampling_rate_hz': 20,
                 'uncertainty': 'source and physical review pending'} for name in names]
    contexts = [{'name': name, 'unit': 'structured',
                 'method': 'independently reviewed source-hashed packet'} for name in
                ('reviewed_site', 'official_device_authority', 'applicable_law_source')]
    return {'channels': channels, 'context_inputs': contexts,
            'limitations': ['No diagnostic fixture proves a physical sign, authority, exception or legal outcome.']}


def build():
    stages = {}
    relevant = {'status': 'draft', 'cell_id': CELL, 'actor': ACTOR,
                'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                   'applies_to': [ACTOR], 'confidence': 'low',
                                   'relevance_type': 'exact official parking-device branch',
                                   'notes': 'Exact sign instruction, authority and governed place require original review.'}],
                'borderline_excluded': []}
    stages['relevance_batch'] = save('relevance_batch', relevant)
    stages['relevance'] = save('relevance', relevant)
    phrases = [
        ('stop, stand or park', 'Actual halt activity needs original motion and independent purpose.'),
        ('official traffic-control devices prohibit stopping, standing or parking',
         'Official device identity, exact instruction and governed place need independent review.'),
        ('necessary to avoid conflict with other traffic',
         'Necessity needs independent original traffic observations.'),
        ('in compliance with law', 'Specific applicable law and compliance need independent source.'),
        ('directions of a police officer or official traffic-control device',
         'Direction and actual compliance need independent original observations.')]
    params = [
        ('halt_action', 'controller', 'park, stop or stand request'),
        ('device_mode', 'world_setup', 'effective or not effective at original halt'),
        ('exception_setup', 'world_setup', 'none, traffic conflict, law, police or device direction'),
        ('exact_instruction', 'world_setup', 'source-reviewed prohibition text'),
        ('parking_site', 'world_setup', 'source-reviewed C229439 road and governed polygon'),
        ('capture_profile', 'world_setup', 'four original RGB cameras at 20 Hz for 900 frames')]
    template = {'law_id': LAW, 'actor': ACTOR, 'template_id': TEMPLATE_ID,
                'quote': QUOTE,
                'structure': {
                    'activation': {'condition': 'Observed stopping, standing or parking at a place governed by an effective official prohibition.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'Do not stop, stand or park at a place where an official device prohibits that act, absent a statutory exception.',
                                   'numeric_conditions': []},
                    'exceptions': [
                        {'source_clause': 'necessary to avoid conflict with other traffic',
                         'trigger': 'necessary traffic conflict', 'effect': 'exception may apply',
                         'description': 'Observe other traffic and why the halt was necessary.'},
                        {'source_clause': 'in compliance with law', 'trigger': 'specific applicable law',
                         'effect': 'exception may apply',
                         'description': 'Identify source law and actual compliant conduct.'},
                        {'source_clause': 'directions of a police officer', 'trigger': 'police direction',
                         'effect': 'exception may apply',
                         'description': 'Observe the officer direction and actual compliance.'},
                        {'source_clause': 'official traffic-control device', 'trigger': 'device direction',
                         'effect': 'exception may apply',
                         'description': 'Observe the distinct official direction and actual compliance.'}],
                    'timing': {'description': 'Compare original device effective conditions to each original halt frame.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in phrases]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in params], 'status': 'draft'}
    stages['template'] = save('template', template)
    observed_names = ('actual_halt_activity', 'official_device_instruction',
                      'exception_circumstances', 'exception_circumstances',
                      'exception_circumstances')
    judgment_refs = []
    for index, ((phrase, note), observable) in enumerate(zip(phrases, observed_names), 1):
        desc = {'name': observable, 'unit': 'structured',
                'description': 'Original Native observations and independent source context for ' + phrase + '.'}
        context_name = 'official_device_authority' if index == 2 else 'applicable_law_source'
        judgment_refs.append(save('judgment-' + str(index),
            {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
             'observable_requirements': {'observables': [desc],
                                         'context_inputs': [{'name': context_name, 'unit': 'structured',
                                                             'description': 'Independently reviewed source packet.'}],
                                         'sweep_dimensions': [], 'recording_needs': [desc],
                                         'landmarks': [],
                                         'limitations': ['Original observations do not decide the legal phrase.']},
             'status': 'draft'}))
    stages['judgment_observables'] = judgment_refs
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'established_contexts': ['Assigned road parking cell; exact original site and sign remain source-gated'],
               'fixed_parameters': [{'name': 'assigned_cell', 'value': CELL,
                                     'rationale': 'Frozen catalog identity, not an approved physical site'}],
               'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                        'used_by_laws': [LAW]} for name, kind, domain in params]}
    stages['bindings'] = save('bindings', binding)
    description = recording()
    def values(plan_case):
        mapping = {'halt_action': plan_case['halt_action'],
                   'device_mode': plan_case['device_mode'],
                   'exception_setup': plan_case['exception'],
                   'exact_instruction': plan_case['exact_instruction'],
                   'parking_site': 'reviewed C229439 governed road place',
                   'capture_profile': 'four original RGB views, 20 Hz, 900 frames'}
        return {name: {'kind': kind, 'value': mapping[name]} for name, kind, _ in params}
    baseline = PLAN['cases'][0]
    case_list = [{'case_id': FOLDER.name + '__semantic_baseline',
                  'target_law_id': None, 'target_type': 'baseline',
                  'rationale': 'Shared source-dependent setup reference; no separate recording.',
                  'recording_description': description,
                  'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
                  'variable_assignments': values(baseline)}]
    for item in PLAN['cases']:
        suffix = item['case_id'].rsplit('__', 1)[-1]
        primary = 'device_mode' if suffix in ('park_effective', 'park_not_effective') else (
            'halt_action' if suffix in ('stop_effective', 'stand_effective') else 'exception_setup')
        group = 'device_window' if suffix in ('park_effective', 'park_not_effective') else (
            'traffic_conflict' if suffix in ('stop_effective', 'stop_for_conflict') else suffix)
        differences = [primary]
        if group == 'traffic_conflict': differences = ['exception_setup']
        case_list.append({'case_id': item['case_id'], 'target_law_id': LAW,
                          'target_type': 'boundary_probe', 'paired_probe_id': group,
                          'deliberate_differences': differences,
                          'probe': {'primary_variable': primary,
                                    'comparison_or_standard': group,
                                    'target_value_or_branch': suffix},
                          'rationale': 'Source-dependent original observation probe: ' + suffix,
                          'recording_description': description,
                          'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
                          'variable_assignments': values(item)})
    sweeps = [{'sweep_id': 'pending-' + str(i), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete', 'missing_inputs': [
                   'Reviewed actual sign/site and source-grounded feasible range'],
               'rationale': 'No invented numeric legal cutoff or physical sweep range.'}
              for i, (phrase, note) in enumerate(phrases, 1)]
    stages['cases'] = save('cases', {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                                    'cases': case_list, 'sweep_specs': sweeps,
                                    'sweeps_expanded': True})
    (PROPOSALS / 'semantic-index.json').write_text(json.dumps({
        'format': 'worker-semantic-delivery', 'assignment_id': FOLDER.name,
        'stages': stages}, indent=2) + '\n')
    for entry in json.loads((FOLDER / 'execution-manifest.json').read_text())['cases']:
        path = FOLDER / entry['construction']
        construction = json.loads(path.read_text())
        construction['recording_description'] = description
        path.write_text(json.dumps(construction, indent=2) + '\n')
    return len(case_list)


if __name__ == '__main__':
    print(build())
