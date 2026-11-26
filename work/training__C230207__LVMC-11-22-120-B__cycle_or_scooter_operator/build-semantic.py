"""Author canonical source-faithful signed-roadway semantic proposals."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = json.loads((HERE / 'proposals/cases.json').read_text())
AID = HERE.name
LAW = 'LVMC-11-22-120-B'
ACTOR = 'cycle_or_scooter_operator'
TEXT = ('The City Traffic Engineer is authorized to determine and designate those heavily traveled streets upon which shall be prohibited the use of the roadway by motor-driven cycles, bicycles, horse-drawn vehicles or other nonmotorized traffic and shall erect appropriate signs giving notice thereof. When signs are erected giving notice thereof, no person shall disobey the restriction stated on such signs.')
TID = LAW + '@' + ACTOR
REC = SOURCE['cases'][0]['recording_description']
JUDGMENTS = [
    {'phrase': 'heavily traveled streets', 'note': 'The City Traffic Engineer determination and designation require an original authority source, not a synthetic traffic count.'},
    {'phrase': 'appropriate signs', 'note': 'Sign face, erected position, governed direction and restriction wording require original source and pixel review.'},
]


def write(name, value):
    path = HERE / 'proposals' / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C230207', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': TEXT, 'applies_to': [ACTOR],
                                    'relevance_type': 'direct', 'confidence': 'high',
                                    'notes': 'Frozen signed-roadway travel cell; selected human-propelled bicycle is named, while actual designation, sign and subtype remain source-gated.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    template = {'template_id': TID, 'law_id': LAW, 'actor': ACTOR, 'quote': TEXT,
                'status': 'draft',
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'City Traffic Engineer designates a heavily traveled roadway and an appropriate sign states its restriction.', 'numeric_conditions': []},
                              'obligation': {'type': 'must_not', 'description': 'A person shall not disobey the restriction stated on an erected notice sign.', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'While the sign is erected and governing roadway use.', 'numeric_conditions': []},
                              'judgment_calls_needed': JUDGMENTS},
                'parameter_refs': [{'name': 'designation_context', 'kind': 'world_setup', 'range_or_domain': 'source-reviewed City Traffic Engineer designation'},
                                   {'name': 'signed_restriction', 'kind': 'world_setup', 'range_or_domain': 'reviewed erected sign face, position and direction'},
                                   {'name': 'bicycle_class', 'kind': 'world_setup', 'range_or_domain': 'reviewed human-propelled bicycle subtype'},
                                   {'name': 'commanded_surface', 'kind': 'controller', 'range_or_domain': ['shoulder', 'roadway']},
                                   {'name': 'observed_roadway_use', 'kind': 'subject_behavior', 'range_or_domain': 'source-joined rider footprint after sign'}]}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = []
    for index, judgment in enumerate(JUDGMENTS):
        if index == 0:
            context = [{'name': 'city_designation', 'unit': 'structured', 'description': 'Original City Traffic Engineer determination, roadway scope and effective status.'}]
            recordings = [{'name': 'dev.governs', 'unit': 'structured', 'description': 'Native road and sign scope readback with source link.'}]
        else:
            context = [{'name': 'official_sign_notice', 'unit': 'structured', 'description': 'Original sign wording, erected status and direction reviewed against Native pixels.'}]
            recordings = [{'name': 'dev.regulatory_sign', 'unit': 'structured', 'description': 'Original sign face and wording.'},
                          {'name': 'dev.governs', 'unit': 'structured', 'description': 'Road segment and direction controlled.'}]
        item = {'template_id': TID, 'phrase': judgment['phrase'], 'note': judgment['note'], 'status': 'draft',
                'observable_requirements': {'observables': [{'name': 'rel.occupies', 'unit': 'structured', 'description': 'Original bicycle footprint joined to governed roadway after sign.'}],
                                            'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                                            'recording_needs': recordings,
                                            'limitations': ['No numerical proxy establishes the statutory qualitative phrase; independent original-source review is required.']}}
        refs['judgment_observables'].append(write(f'judgment-observables-{index}.json', item))
    binding = {'cell_id': 'C230207', 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Frozen road travel and access restriction sign cell; actual authority and face remain unverified.'],
               'law_refs': [{'template_id': TID, 'binding_kind': 'direct'}], 'context_refs': [],
               'fixed_parameters': [{'name': 'bicycle_class', 'kind': 'world_setup', 'range_or_domain': 'human-propelled bicycle for both cases', 'used_by_laws': [LAW]}],
               'variable_parameters': [{'name': 'designation_context', 'kind': 'world_setup', 'range_or_domain': 'requested designation pending original review', 'used_by_laws': [LAW]},
                                       {'name': 'signed_restriction', 'kind': 'world_setup', 'range_or_domain': 'same authored sign for both cases pending face review', 'used_by_laws': [LAW]},
                                       {'name': 'commanded_surface', 'kind': 'controller', 'range_or_domain': ['shoulder', 'roadway'], 'used_by_laws': [LAW]},
                                       {'name': 'observed_roadway_use', 'kind': 'subject_behavior', 'range_or_domain': 'original footprint readback', 'used_by_laws': [LAW]}]}
    refs['bindings'] = write('bindings.json', binding)
    cases = []
    for suffix, surface, target in [('probe_01', 'shoulder', 'compliant_attempt'),
                                    ('probe_02', 'roadway', 'violating_attempt')]:
        cases.append({'case_id': AID + '__' + suffix, 'target_law_id': LAW,
                      'target_type': target,
                      'rationale': 'Controlled bicycle surface-choice attempt under the same signed road; legal and authority conclusions remain source-gated.',
                      'variable_assignments': {'designation_context': {'kind': 'world_setup', 'value': 'requested_designation_pending_review'},
                                               'signed_restriction': {'kind': 'world_setup', 'value': 'authored_bicycles_prohibited_roadway_sign_pending_pixel_review'},
                                               'commanded_surface': {'kind': 'controller', 'value': surface},
                                               'observed_roadway_use': {'kind': 'subject_behavior', 'value': None}},
                      'unresolved_judgment_calls': [j['phrase'] for j in JUDGMENTS],
                      'recording_description': REC,
                      'paired_probe_id': AID + '__surface_choice',
                      'deliberate_differences': ['commanded_surface'],
                      'probe': {'primary_variable': 'commanded_surface',
                                'comparison_or_standard': 'Original bicycle footprint on shoulder versus roadway after same sign',
                                'target_value_or_branch': surface},
                      'deterministic_branch': {'source_clause': 'When signs are erected giving notice thereof, no person shall disobey the restriction stated on such signs.',
                                               'judgment_context': [{'phrase': j['phrase'], 'note': j['note'], 'status': 'fixed_assumption',
                                                                     'reason': 'Both cases request one fixed source-reviewed designation and sign; verify originals after Native capture.',
                                                                     'world_setup_refs': ['designation_context', 'signed_restriction']}
                                                                    for j in JUDGMENTS]}})
    baseline = {'case_id': AID + '__neutral_baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Unselected shared sign and roadway reference without a legal label.',
                'variable_assignments': {'designation_context': {'kind': 'world_setup', 'value': 'requested_designation_pending_review'},
                                         'signed_restriction': {'kind': 'world_setup', 'value': 'authored_bicycles_prohibited_roadway_sign_pending_pixel_review'},
                                         'commanded_surface': {'kind': 'controller', 'value': 'shoulder'},
                                         'observed_roadway_use': {'kind': 'subject_behavior', 'value': None}},
                'unresolved_judgment_calls': [], 'recording_description': REC}
    sweep = {'sweep_id': 'LVMC-11-22-120-B-designation-and-sign-review',
             'target_law_id': LAW, 'judgment_refs': JUDGMENTS, 'status': 'incomplete',
             'rationale': 'Qualitative designation and appropriate sign require original authority and physical face review.',
             'missing_inputs': ['Original City Traffic Engineer designation and actual sign face/location/direction are absent from frozen inputs.']}
    proposal = {'cell_id': 'C230207', 'actor': ACTOR, 'status': 'draft',
                'sweeps_expanded': True, 'sweep_specs': [sweep], 'cases': [baseline] + cases}
    refs['cases'] = write('cases.json', proposal)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID, 'stages': refs})
    print(json.dumps({'selected_cases': [item['case_id'] for item in cases],
                      'judgments': [j['phrase'] for j in JUDGMENTS]}, sort_keys=True))


if __name__ == '__main__':
    main()
