"""Build draft canonical stage proposals from exact selected driveway cases.

Unconstructed exception sweeps remain explicitly incomplete; these drafts
make no physical or legal acceptance claim.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
LAW = 'LVMC-11-52-130-A7'
ACTOR = 'motor_vehicle_driver'
PROPOSALS = ROOT / 'proposals'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((REPO / 'inputs' / AID / 'assignment.json').read_text())
    law_text = assignment['law']['text']
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    ids = [item['case_id'] for item in manifest['cases']]
    relevance = {'status': 'draft', 'cell_id': 'C150094', 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW, 'quote': law_text,
                                    'applies_to': [ACTOR], 'confidence': 'high',
                                    'relevance_type': 'specific_match',
                                    'notes': 'Driveway stopping or parking on the one-way road is an applicable source question; original geometry and authority require local review.'}],
                 'borderline_excluded': []}
    references = {'relevance': save(PROPOSALS / 'relevance.json', relevance),
                  'relevance_batch': save(PROPOSALS / 'relevance_batch.json', relevance)}
    judgments = [
        ('necessary to avoid conflict with other traffic', 'Necessity requires original traffic context and a reason for the stop.', 'drv.standing_or_parked'),
        ('in compliance with law', 'An applicable source of law and the reason for the stop must be declared.', 'drv.standing_or_parked'),
        ('the directions of a police officer or a traffic control device', 'Officer authority or a governing device instruction must be reviewed independently.', 'dev.regulatory_sign'),
        ('owns or is in control of that driveway, or who is a family member or invitee', 'Private authority role and relationship need a specific reviewed source declaration.', 'rel.occupies'),
        ('while it is being operated on official business', 'USPS vehicle identity and official-business purpose are separate source facts.', 'ru.official_vehicle'),
    ]
    template_id = LAW + '@' + ACTOR
    template = {'status': 'draft', 'law_id': LAW, 'actor': ACTOR,
                'template_id': template_id, 'quote': law_text, 'parameter_refs': [],
                'structure': {
                    'activation': {'description': 'Stop, stand or park in front of a driveway or within its five-foot side band; public and private driveways are both named.',
                                   'source_clause': 'In front of or within five feet of a public or private driveway',
                                   'side_band': {'variable': 'observed_gap_m', 'operator': '<=', 'value': 1.524, 'unit': 'm',
                                                 'description': 'Five feet expressed in metres; exact equality is included. Front overlap is a separate alternative.'}},
                    'obligation': {'type': 'prohibition', 'source_clause': 'No person shall stop, stand or park a vehicle',
                                   'description': 'Retain each action separately and test the stated source exceptions.'},
                    'exceptions': [
                        {'source_clause': 'when necessary to avoid conflict with other traffic', 'description': 'Source-reviewed conflict necessity.'},
                        {'source_clause': 'in compliance with law', 'description': 'Source-reviewed applicable legal obligation.'},
                        {'source_clause': 'the directions of a police officer or a traffic control device', 'description': 'Source-reviewed officer or device direction.'},
                        {'source_clause': 'this provision does not apply to the parking of a vehicle in or near a private driveway by a person who owns or is in control of that driveway, or who is a family member or invitee of the person so owning or controlling the driveway', 'description': 'Parking-only private driveway authority; roles require separate facts.'},
                        {'source_clause': 'do not apply to a United States Postal Service vehicle while it is being operated on official business', 'description': 'USPS vehicle on official business.'}],
                    'timing': {'description': 'Join original pose, body footprint, driveway context and four videos over the full 20 Hz, 30 s capture.'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments]}}
    references['template'] = save(PROPOSALS / 'template.json', template)
    observed = []
    for index, (phrase, note, channel) in enumerate(judgments):
        evidence = {'status': 'draft', 'template_id': template_id, 'phrase': phrase, 'note': note,
                    'observable_requirements': {
                        'observables': [{'name': channel, 'unit': 'structured', 'description': 'Retain the original frame-joined measurement without converting it into a legal judgment.'}],
                        'context_inputs': [{'name': 'driveway_context', 'unit': 'structured', 'description': 'Require source-declared driveway kind, authority and exception facts with provenance.'}],
                        'sweep_dimensions': [], 'landmarks': [],
                        'recording_needs': [{'name': channel, 'unit': 'structured', 'description': 'Retain the source-joined Native observation for independent review.'}],
                        'limitations': [note, 'Synthetic fixtures cannot establish the original legal or physical fact.']}}
        observed.append(save(PROPOSALS / f'judgment_observables_{index}.json', evidence))
    references['judgment_observables'] = observed
    variables = [
        {'name': 'target_gap_m', 'kind': 'controller', 'range_or_domain': 'authored positive body-gap target in metres', 'used_by_laws': [LAW]},
        {'name': 'observed_gap_m', 'kind': 'subject_behavior', 'range_or_domain': 'original Native measured body gap in metres', 'used_by_laws': [LAW]},
        {'name': 'private_authority_role', 'kind': 'world_setup', 'range_or_domain': 'none, owner, controller, family member, invitee; source declaration required', 'used_by_laws': [LAW]},
        {'name': 'driveway_kind', 'kind': 'world_setup', 'range_or_domain': 'public or private; independently reviewed', 'used_by_laws': [LAW]},
    ]
    binding = {'status': 'draft', 'cell_id': 'C150094', 'actor': ACTOR,
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'established_contexts': [], 'fixed_parameters': [],
               'variable_parameters': variables}
    references['bindings'] = save(PROPOSALS / 'bindings.json', binding)
    recs = {item['case_id']: json.loads((ROOT / item['construction']).read_text())['recording_description'] for item in manifest['cases']}
    common_recording = recs[ids[0]]
    all_phrases = [item[0] for item in judgments]
    def assignments(gap, role='none'):
        return {'target_gap_m': {'kind': 'controller', 'value': gap, 'unit': 'm'},
                'observed_gap_m': {'kind': 'subject_behavior', 'value': None, 'unit': 'm'},
                'private_authority_role': {'kind': 'world_setup', 'value': role, 'unit': 'categorical'},
                'driveway_kind': {'kind': 'world_setup', 'value': 'private', 'unit': 'categorical'}}
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
                'rationale': 'Common surveyed one-way route and driveway source context.',
                'recording_description': common_recording,
                'variable_assignments': assignments(None),
                'unresolved_judgment_calls': all_phrases}
    cases = [baseline]
    for number, gap, branch in [('01', 2.0, 'above'), ('02', 1.2, 'below'),
                                ('03', 1.2, 'owner'), ('04', 1.524, 'at')]:
        case_id = AID + '__probe_' + number
        role = 'owner' if number == '03' else 'none'
        comparison = 'private_authority' if number == '03' else 'five_feet_boundary'
        probe = {'primary_variable': 'private_authority_role' if number == '03' else 'observed_gap_m',
                 'comparison_or_standard': 'private authority source contrast' if number == '03' else 'five-foot body-gap side-band boundary',
                 'target_value_or_branch': branch}
        if number != '03':
            probe.update({'threshold_ref': 'activation.side_band', 'operator': '<=',
                          'unit': 'm', 'test_value': gap})
        cases.append({'case_id': case_id, 'target_law_id': LAW, 'target_type': 'boundary_probe',
                      'rationale': 'Exact selected source-measured driveway '+branch+' probe.',
                      'recording_description': recs[case_id],
                      'variable_assignments': assignments(gap, role),
                      'unresolved_judgment_calls': all_phrases,
                      'paired_probe_id': comparison,
                      'deliberate_differences': ['private_authority_role'] if number == '03' else ['target_gap_m'],
                      'probe': probe,
                      'epsilon_used': {'value': 0.05, 'unit': 'm',
                                       'rationale': 'Physical controller target margin only; exact legal boundary remains five feet.'}})
    sweep_specs = [{'sweep_id': 'pending-'+str(i), 'status': 'incomplete', 'target_law_id': LAW,
                    'judgment_refs': [{'phrase': phrase, 'note': note}],
                    'rationale': 'Retain this statutory judgment as an explicit unresolved source requirement.',
                    'missing_inputs': ['Selected branch construction and source-reviewed original exception evidence are pending.']}
                   for i, (phrase, note, _) in enumerate(judgments)]
    case_stage = {'status': 'draft', 'cell_id': 'C150094', 'actor': ACTOR,
                  'cases': cases, 'sweep_specs': sweep_specs, 'sweeps_expanded': True}
    references['cases'] = save(PROPOSALS / 'canonical-cases.json', case_stage)
    save(PROPOSALS / 'semantic-index.json', {'format': 'worker-semantic-delivery',
                                              'assignment_id': AID, 'stages': references})
    print(json.dumps({'stage_refs': len(references), 'selected_cases': len(cases)-1}))


if __name__ == '__main__':
    main()
