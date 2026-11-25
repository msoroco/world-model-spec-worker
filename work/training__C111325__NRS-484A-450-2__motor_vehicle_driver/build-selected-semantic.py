"""Canonical draft stages for the selected near-side crosswalk attempt pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
PROPOSALS = HERE / 'proposals'
LAW_ID, ACTOR = ASSIGNMENT['law_id'], ASSIGNMENT['actor']
TEMPLATE = f'{LAW_ID}@{ACTOR}'
QUOTE = ASSIGNMENT['law']['text']


def write(name, data):
    path = PROPOSALS / name
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    PROPOSALS.mkdir(exist_ok=True)
    relevance = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': QUOTE,
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'low',
                                    'notes': 'Frozen signed intersection approach; original sign, near-side crosswalk and stop require source review.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    template = {'template_id': TEMPLATE, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': QUOTE,
                'structure': {
                    'activation': {'description': 'Driver approaches a stop intersection indicated by a governing stop sign',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must', 'description': 'Stop before the near-side crosswalk; if absent, before the clearly marked stop line; if both absent, at the nearest point with a view of approaching intersecting traffic before entering the intersection',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'The full vehicle body must halt before the applicable reference and before intersection entry',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [],
                },
                'parameter_refs': [
                    {'name': 'near_side_crosswalk_present', 'kind': 'world_setup',
                     'range_or_domain': 'true for crosswalk cases, false for no-crosswalk marked-line cases'},
                    {'name': 'requested_pre_crosswalk_stop', 'kind': 'controller',
                     'range_or_domain': 'true or false; request is not measured behavior'},
                    {'name': 'requested_pre_line_stop', 'kind': 'controller',
                     'range_or_domain': 'true or false when the marked-line branch applies'},
                    {'name': 'measured_pre_crosswalk_stop', 'kind': 'subject_behavior',
                     'range_or_domain': 'source-measured Boolean; no legal conclusion'},
                ]}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = []
    binding = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [{'name': 'C111325 signed near-side approach',
                                         'source': 'Frozen catalog cell; physical governing sign and crosswalk require original review'}],
               'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [
                   {'name': 'near_side_crosswalk_present', 'kind': 'world_setup',
                    'range_or_domain': 'true/false by selected statutory branch', 'used_by_laws': [LAW_ID]},
                   {'name': 'requested_pre_crosswalk_stop', 'kind': 'controller',
                    'range_or_domain': 'true/false', 'used_by_laws': [LAW_ID]},
                   {'name': 'requested_pre_line_stop', 'kind': 'controller',
                    'range_or_domain': 'true/false on the marked-line branch', 'used_by_laws': [LAW_ID]},
                   {'name': 'measured_pre_crosswalk_stop', 'kind': 'subject_behavior',
                    'range_or_domain': 'source-measured true/false', 'used_by_laws': [LAW_ID]}]}
    refs['bindings'] = write('bindings.json', binding)
    description = json.loads((HERE / 'selected-probe-1-primary-construction.json').read_text())['recording_description']
    assignments = lambda requested, crosswalk=True: {
        'near_side_crosswalk_present': {'kind': 'world_setup', 'value': crosswalk, 'unit': 'boolean'},
        'requested_pre_crosswalk_stop': {'kind': 'controller', 'value': requested if crosswalk else None, 'unit': 'boolean'},
        'requested_pre_line_stop': {'kind': 'controller', 'value': requested if not crosswalk else None, 'unit': 'boolean'},
        'measured_pre_crosswalk_stop': {'kind': 'subject_behavior', 'value': None, 'unit': 'boolean'},
    }
    cases = {'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR, 'status': 'draft',
             'sweep_specs': [], 'cases': [
                 {'case_id': HERE.name + '__baseline_reference', 'target_law_id': None,
                  'target_type': 'baseline', 'rationale': 'Shared signed approach context; no extra recording',
                  'variable_assignments': assignments(False),
                  'recording_description': description,
                  'unresolved_judgment_calls': [], 'reuse_case_id': HERE.name + '__probe_2'},
                 *[{'case_id': HERE.name + f'__probe_{index}',
                    'target_law_id': LAW_ID,
                    'target_type': 'compliant_attempt' if index == 1 else 'violating_attempt',
                    'paired_probe_id': HERE.name + '__comparison',
                    'deliberate_differences': ['requested_pre_crosswalk_stop'],
                    'probe': {'primary_variable': 'requested_pre_crosswalk_stop',
                              'comparison_or_standard': 'source-measured full body halt before the near-side crosswalk; no legal verdict',
                              'target_value_or_branch': requested},
                    'rationale': 'Controlled requested stop comparison; realized body and speed are measured after capture',
                    'variable_assignments': assignments(requested),
                    'recording_description': description,
                    'unresolved_judgment_calls': []}
                   for index, requested in ((1, True), (2, False))],
                 *[{'case_id': HERE.name + '__' + label,
                    'target_law_id': LAW_ID,
                    'target_type': 'compliant_attempt' if requested else 'violating_attempt',
                    'paired_probe_id': HERE.name + '__marked_line_comparison',
                    'deliberate_differences': ['requested_pre_line_stop'],
                    'probe': {'primary_variable': 'requested_pre_line_stop',
                              'comparison_or_standard': 'source-measured full body halt before marked line with no crosswalk; no legal verdict',
                              'target_value_or_branch': requested},
                    'rationale': 'No-crosswalk marked-line controlled request; physical line rendering and actual halt need original review',
                    'variable_assignments': assignments(requested, False),
                    'recording_description': description,
                    'unresolved_judgment_calls': []}
                   for label, requested in (('line_stop', True), ('line_pass', False))],
             ]}
    refs['cases'] = write('cases.json', cases)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name,
                                  'status': 'draft', 'stages': refs})
    return {'selected_cases': 4, 'index_sha256': refs['cases']['sha256']}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
