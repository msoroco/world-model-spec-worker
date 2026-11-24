"""Author the source-qualified semantic chain for the two selected device cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'
ASSIGNMENT = json.loads((HERE.parents[1] / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
TEMPLATE = LAW_ID + '@' + ACTOR
QUOTE = LAW['text']
PARAM = 'commanded_stop_request'
JUDGMENTS = [
    {'phrase': 'official traffic-control device placed in accordance with the provisions of chapters 484A to 484E, inclusive, of NRS',
     'note': 'Original device identity, applicability, official placement and source provenance require review.'},
    {'phrase': 'Except as otherwise provided in NRS 484B.307',
     'note': 'Signal-specific exception applicability requires source-qualified review.'},
    {'phrase': 'unless at the time otherwise directed by a police officer',
     'note': 'Original officer authority, contemporaneous direction and applicability require review.'},
]


def write(name, value):
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
             'relevant_laws': [{'law_id': LAW_ID, 'quote': QUOTE, 'applies_to': [ACTOR],
                                'relevance_type': 'direct', 'confidence': 'high',
                                'notes': 'Frozen traffic-control-device alley travel directly invokes this driver instruction; authority and exceptions remain unresolved.'}],
             'borderline_excluded': []}
r_batch = write('relevance-batch.json', relevance)
r_cell = write('relevance.json', relevance)
template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR,
            'quote': QUOTE, 'status': 'draft',
            'structure': {'law_id': LAW_ID,
                          'activation': {'condition': 'Driver encounters an applicable official traffic-control device.', 'numeric_conditions': []},
                          'obligation': {'type': 'must', 'description': 'Obey the instructions of that device when the statutory exceptions do not apply.', 'numeric_conditions': []},
                          'exceptions': [
                              {'source_clause': 'Except as otherwise provided in NRS 484B.307', 'description': 'NRS 484B.307 applicability remains source-qualified.'},
                              {'source_clause': 'unless at the time otherwise directed by a police officer', 'description': 'Contemporaneous police officer direction remains source-qualified.'}],
                          'timing': {'description': 'Evaluate device instruction and contemporaneous driver response from original time-joined sources.', 'numeric_conditions': []},
                          'judgment_calls_needed': JUDGMENTS},
            'parameter_refs': [{'name': PARAM, 'kind': 'controller', 'range_or_domain': 'authored stop request at device station, 0 or 1'}]}
r_template = write('template.json', template)
r_judgments = []
for i, judgment in enumerate(JUDGMENTS):
    observable = {'template_id': TEMPLATE, **judgment, 'status': 'draft',
                  'observable_requirements': {
                      'observables': [{'name': 'device_body', 'unit': 'structured',
                                       'description': 'Original device and ego body frame-joined source observations'}],
                      'context_inputs': [],
                      'sweep_dimensions': [{'name': PARAM, 'unit': 'structured',
                                            'description': 'Authored stop or proceed request, independent of observed behavior'}],
                      'landmarks': [],
                      'recording_needs': [{'name': 'device_body', 'unit': 'structured',
                                           'description': 'Retain original Native body and device source identity'}],
                      'limitations': ['Synthetic CPU records do not establish official placement, officer direction, NRS 484B.307 applicability or a legal outcome.']}}
    r_judgments.append(write(f'judgment-{i}.json', observable))
binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
           'established_contexts': ['Frozen alley travel with an authored traffic-control-device stop station; original authority and applicability are unverified.'],
           'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
           'context_refs': [], 'fixed_parameters': [],
           'variable_parameters': [{'name': PARAM, 'kind': 'controller',
                                    'range_or_domain': 'authored 0 or 1 stop request', 'used_by_laws': [LAW_ID]}]}
r_bindings = write('bindings.json', binding)
original_cases = json.loads((PROPOSALS / 'cases.json').read_text())['cases']
recording = original_cases[0]['recording_description']
baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None,
            'target_type': 'baseline', 'rationale': 'Reference authored device station with no legal outcome.',
            'variable_assignments': {PARAM: {'kind': 'controller', 'value': 1.0, 'unit': 'structured'}},
            'recording_description': recording, 'unresolved_judgment_calls': []}
cases = [baseline]
for index, original in enumerate(original_cases):
    point = float(1 - index)
    cases.append({'case_id': original['case_id'], 'target_law_id': LAW_ID,
                  'target_type': 'judgment_sweep',
                  'rationale': 'Compare authored stop and proceed requests at one fixed device station while leaving authority and legal judgments unresolved.',
                  'paired_probe_id': 'c10389-device-response',
                  'deliberate_differences': [PARAM],
                  'probe': {'primary_variable': PARAM,
                            'comparison_or_standard': 'physical coverage; legal judgment unresolved',
                            'target_value_or_branch': {PARAM: point}},
                  'sweep_id': 'c10389-device-response', 'sweep_spec_version': '',
                  'sweep_point': {PARAM: point}, 'selection_rank': index,
                  'variable_assignments': {PARAM: {'kind': 'controller', 'value': point, 'unit': 'structured'}},
                  'recording_description': original['recording_description'],
                  'judgment_refs': JUDGMENTS,
                  'unresolved_judgment_calls': [j['phrase'] for j in JUDGMENTS]})
spec = {'sweep_id': 'c10389-device-response', 'target_law_id': LAW_ID,
        'judgment_refs': JUDGMENTS,
        'rationale': 'Physically sample authored stop and proceed requests; all legal judgments remain unresolved.',
        'status': 'complete', 'mode': 'one_dimensional', 'landmarks': [],
        'axes': [{'variable': PARAM, 'observable': PARAM, 'unit': 'structured',
                  'min': 0.0, 'max': 1.0, 'spacing': 1.0,
                  'range_rationale': 'The two authored device responses are proceed and stop.',
                  'spacing_rationale': 'The binary authored request has two feasible states.',
                  'feasibility_evidence': 'Retained 600-frame synthetic fixtures for both requests.',
                  'measurement': {'method': 'Retain commanded request and original body response separately',
                                  'time_window': 'entire 30 s attempt', 'statistic': 'first'}}],
        'variable_assignments': {PARAM: {'kind': 'controller', 'value': 1.0, 'unit': 'structured'}},
        'recording_description': recording,
        'spec_version': '', 'planned_case_count': 2,
        'selection_order': [c['case_id'] for c in cases[1:]]}
# The fixed binary grid visits 0 before 1; preserve that selection order.
cases[1], cases[2] = cases[2], cases[1]
spec['selection_order'] = [c['case_id'] for c in cases[1:]]
cases[1]['selection_rank'], cases[2]['selection_rank'] = 0, 1
semantic_cases = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                  'cases': cases, 'sweep_specs': [spec], 'sweeps_expanded': True}
r_cases = write('canonical-cases.json', semantic_cases)
index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
         'status': 'draft_source_qualified_judgment_pending',
         'stages': {'relevance_batch': r_batch, 'relevance': r_cell,
                    'template': r_template, 'judgment_observables': r_judgments,
                    'bindings': r_bindings, 'cases': r_cases}}
write('semantic-index.json', index)
print('semantic-index.json authored')
