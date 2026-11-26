"""Build draft canonical semantic stages for the four exact flagger probes."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = ROOT.name
INPUT = Path('inputs') / ASSIGNMENT / 'assignment.json'
PHRASES = (
    ('authorized flagger', 'Authority and traffic-control role require independent source review.',
     'dev.human_direction', 'flagger_authority_and_governance'),
    ('clearly marked area of highway construction or maintenance or any other area which has been designated as a temporary traffic control zone',
     'The two statutory location alternatives require separate source review.',
     'dev.temporary_traffic_control', 'statutory_location_basis'),
    ('any signal', 'The indication and governed approach require original pixel review.',
     'dev.governs', 'flagger_authority_and_governance'),
    ('fail or refuse to comply', 'Response order is measurable; legal meaning and intent remain unresolved.',
     'motorcycle_response', 'flagger_authority_and_governance'),
)


def write(name, obj):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads(INPUT.read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    law, actor, cell = assignment['law'], assignment['actor'], assignment['cell_id']
    template_id = law['id'] + '@' + actor
    relevance = {
        'cell_id': cell, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law['id'], 'quote': law['text'],
                           'applies_to': [actor], 'relevance_type': 'specific_match',
                           'confidence': 'medium',
                           'notes': 'Fixed flagger cell and motorcycle operator; authority, marking and visible indication require original review.'}],
        'borderline_excluded': [],
    }
    stages = {'relevance_batch': write('relevance_batch.json', relevance),
              'relevance': write('relevance.json', relevance)}
    template = {
        'template_id': template_id, 'law_id': law['id'], 'actor': actor,
        'status': 'draft', 'quote': law['text'],
        'structure': {
            'law_id': law['id'],
            'activation': {'condition': 'Driver of a vehicle faces a signal of an authorized traffic-control flagger in either statutory area.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Comply with the governing signal while it applies.',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Signal precedes judged conduct; response is followed until release.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in PHRASES],
        },
        'parameter_refs': [],
    }
    stages['template'] = write('template.json', template)
    judgments = []
    for index, (phrase, note, channel, context) in enumerate(PHRASES, 1):
        obj = {
            'template_id': template_id, 'phrase': phrase, 'note': note,
            'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'structured',
                                 'description': 'Retain original joined observation with source and frame identity.'}],
                'context_inputs': [{'name': context, 'unit': 'structured',
                                    'description': 'Independently reviewed and sealed source packet.'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'structured',
                                     'description': 'Original observation stream; requested controller state alone is insufficient.'}],
                'limitations': ['Source authority, pixels, physical realization and legal interpretation remain unresolved.'],
            },
        }
        judgments.append(write(f'judgment_{index}.json', obj))
    stages['judgment_observables'] = judgments
    bindings = {
        'cell_id': cell, 'actor': actor, 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [
            {'name': 'reviewed_flagger_context', 'kind': 'world_setup',
             'range_or_domain': 'designated temporary zone or clearly marked work area; original source review pending',
             'used_by_laws': [law['id']]},
            {'name': 'response_policy', 'kind': 'controller',
             'range_or_domain': 'hold until release or cross during requested stop',
             'used_by_laws': [law['id']]},
            {'name': 'observed_response', 'kind': 'subject_behavior',
             'range_or_domain': 'source-joined motorcycle motion and signal; unknown before capture',
             'used_by_laws': [law['id']]},
        ],
    }
    stages['bindings'] = write('bindings.json', bindings)
    cases = []
    first_description = json.loads((ROOT / plan['cases'][0]['draft_construction']).read_text())['recording_description']
    cases.append({
        'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'cell_id': cell, 'actor': actor,
        'rationale': 'Shared semantic context only; no extra recording or accepted evidence.',
        'recording_description': first_description,
        'variable_assignments': {
            'reviewed_flagger_context': {'kind': 'world_setup', 'value': 'designated temporary zone; source review pending', 'unit': 'structured'},
            'response_policy': {'kind': 'controller', 'value': 'hold_until_release', 'unit': 'structured'},
            'observed_response': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'},
        },
        'unresolved_judgment_calls': [p for p, _, _, _ in PHRASES],
    })
    for item in plan['cases']:
        suffix = item['case_id'].rsplit('__', 1)[-1]
        work_area = suffix in ('probe_c', 'probe_d')
        context = ('clearly marked work area' if work_area else 'designated temporary zone') + '; source review pending'
        description = json.loads((ROOT / item['draft_construction']).read_text())['recording_description']
        judgment_context = [{'phrase': p, 'note': n, 'status': 'not_exercised',
                             'reason': 'No original authority, pixels or legal judgment has been reviewed.'}
                            for p, n, _, _ in PHRASES]
        cases.append({
            'case_id': item['case_id'], 'target_law_id': law['id'],
            'target_type': item['target_type'], 'cell_id': cell, 'actor': actor,
            'rationale': item['physical_target'] + ' in the ' + context,
            'recording_description': description,
            'variable_assignments': {
                'reviewed_flagger_context': {'kind': 'world_setup', 'value': context, 'unit': 'structured'},
                'response_policy': {'kind': 'controller', 'value': item['controller_policy'], 'unit': 'structured'},
                'observed_response': {'kind': 'subject_behavior', 'value': None, 'unit': 'structured'},
            },
            'unresolved_judgment_calls': [p for p, _, _, _ in PHRASES],
            'paired_probe_id': 'flagger_work_area_response' if work_area else 'flagger_zone_response',
            'deliberate_differences': ['response_policy'],
            'probe': {'primary_variable': 'response_policy',
                      'comparison_or_standard': 'response to the same requested flagger signal',
                      'target_value_or_branch': item['controller_policy']},
            'deterministic_branch': {
                'source_clause': 'fail or refuse to comply with any signal',
                'judgment_context': judgment_context,
            },
        })
    sweep_specs = [{
        'sweep_id': f'flagger_judgment_{index}', 'target_law_id': law['id'],
        'judgment_refs': [{'phrase': p, 'note': n}],
        'rationale': 'Preserve the qualitative phrase for original-source review; no numeric legal cutoff is invented.',
        'status': 'incomplete',
        'missing_inputs': ['Original reviewed authority and zone sources, signal pixels and physical Native observations.'],
    } for index, (p, n, _, _) in enumerate(PHRASES, 1)]
    stage_cases = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                   'sweep_specs': sweep_specs, 'sweeps_expanded': True, 'cases': cases}
    stages['cases'] = write('cases.json', stage_cases)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
             'stages': stages}
    write('semantic-index.json', index)
    return {'cases': len(cases) - 1, 'judgment_phrases': len(judgments)}


if __name__ == '__main__':
    print(json.dumps(build()))
