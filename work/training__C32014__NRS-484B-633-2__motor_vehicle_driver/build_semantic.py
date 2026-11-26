"""Author draft canonical stages while retaining Department judgment uncertainty."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
CELL = ASSIGNMENT['cell_id']
PHRASE = 'maximum speed which can be maintained with safety to the bridge or structure'
NOTE = 'The Department investigation and declaration are independent administrative sources; authored sign metadata does not establish the safe maximum.'
QUOTE = 'It is unlawful for any person to drive a vehicle over any bridge or other elevated structure constituting a part of a highway at a speed which is greater than the maximum speed which can be maintained with safety to the bridge or structure, when such structure is signposted as provided in this section'


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'borderline_excluded': [],
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE, 'applies_to': [ACTOR],
                                    'relevance_type': 'specific_match', 'confidence': 'high',
                                    'notes': 'Frozen bridge travel cell; original authority and postings need separate source review.'}]}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW, 'actor': ACTOR,
                'quote': QUOTE, 'status': 'draft',
                'structure': {
                    'activation': {'condition': 'a person drives over a bridge or elevated highway structure signposted as provided in the section', 'numeric_conditions': []},
                    'obligation': {'type': 'must_not', 'description': 'drive over that structure faster than the Department-determined safe maximum',
                                   'source_clause': QUOTE, 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'while the vehicle occupies the structure', 'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': [
                    {'name': 'ego_speed', 'kind': 'subject_behavior', 'range_or_domain': 'observed original Native velocity magnitude during structure occupancy'},
                    {'name': 'commanded_approach_speed', 'kind': 'controller', 'range_or_domain': 'physical request in m/s, separate from measured speed'}]}
    refs['template'] = write('template.json', template)
    observable = {'template_id': template['template_id'], 'phrase': PHRASE, 'note': NOTE, 'status': 'draft',
                  'observable_requirements': {
                      'observables': [{'name': 'original_velocity_position', 'unit': 'structured',
                                       'description': 'original on-structure position and velocity per frame'}],
                      'context_inputs': [],
                      'sweep_dimensions': [{'name': 'commanded_approach_speed', 'unit': 'm/s',
                                            'description': 'physical speed request, with observed speed retained separately'}],
                      'landmarks': [],
                      'recording_needs': [{'name': 'structure_sign_survey', 'unit': 'structured',
                                           'description': 'original bridge shape, sign position, orientation, value and native readback'}],
                      'limitations': ['Department determination requires an independent original record',
                                      'Authored 25 mph sign metadata is not a legal safe-speed determination',
                                      'Physical sign faces and bridge mesh require original pixel review']}}
    refs['judgment_observables'] = [write('judgment-bridge-safe-speed.json', observable)]
    bindings = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'established_contexts': [],
                'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
                'context_refs': [],
                'fixed_parameters': [{'name': 'bridge_context', 'value': 'authored C32014 elevated road with two 25 mph 100-foot sign metadata records',
                                      'rationale': 'This is an engineering fixture. Department determination and visible faces remain unresolved.'}],
                'variable_parameters': [
                    {'name': 'ego_speed', 'kind': 'subject_behavior', 'range_or_domain': 'original post-tick speed over elevated structure', 'used_by_laws': [LAW]},
                    {'name': 'commanded_approach_speed', 'kind': 'controller', 'range_or_domain': '9.0 or 13.0 m/s requested; no attainment guarantee', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings.json', bindings)
    original = json.loads((HERE / 'draft-bridge' / 'below_posted_structure_speed' / 'primary/construction.json').read_text())
    description = original['recording_description']
    baseline = {'case_id': HERE.name + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Neutral frozen bridge travel context, not a selected recording.',
                'variable_assignments': {'ego_speed': {'kind': 'subject_behavior', 'value': None},
                                         'commanded_approach_speed': {'kind': 'controller', 'value': None}},
                'unresolved_judgment_calls': [PHRASE], 'recording_description': description}
    cases = [baseline]
    for suffix, speed in (('probe_01', 9.0), ('probe_02', 13.0)):
        cases.append({'case_id': HERE.name + '__' + suffix, 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': 'Compare physical speed requests around the authored posting; original measured speed and Department authority remain separate.',
                      'variable_assignments': {'ego_speed': {'kind': 'subject_behavior', 'value': None},
                                               'commanded_approach_speed': {'kind': 'controller', 'value': speed}},
                      'unresolved_judgment_calls': [PHRASE], 'paired_probe_id': 'bridge_speed_request_pair',
                      'deliberate_differences': ['commanded_approach_speed'],
                      'probe': {'primary_variable': 'commanded_approach_speed',
                                'comparison_or_standard': 'same authored bridge and posting; original on-deck speed measured without legal labeling',
                                'target_value_or_branch': speed},
                      'recording_description': description})
    case_stage = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': cases,
                  'sweep_specs': [{'sweep_id': 'bridge_safe_speed_authority', 'target_law_id': LAW,
                                   'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                                   'status': 'incomplete', 'rationale': 'The Department structural determination is not supplied; two engineering requests cannot resolve it.',
                                   'missing_inputs': ['Independent Department investigation and declaration for this structure',
                                                      'Original source and pixel review of qualifying bridge and maintained signs']}],
                  'sweeps_expanded': True}
    refs['cases'] = write('cases.json', case_stage)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': HERE.name, 'stages': refs})
    print(json.dumps({'selected_case_ids': [c['case_id'] for c in cases[1:]],
                      'judgment_status': 'unresolved_without_Department_source'}))


if __name__ == '__main__':
    main()
