"""Author source-grounded red-curb stage proposals for local review."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = Path(__file__).resolve().parent
INPUT = ROOT / 'inputs' / WORK.name / 'assignment.json'
LAW = json.loads(INPUT.read_text())['law']
STAGE = WORK / 'proposals'
TEMPLATE_ID = LAW['id'] + '@motor_vehicle_driver'


def write(name, value):
    path = STAGE / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    law_id = LAW['id']
    relevance = {'actor': 'motor_vehicle_driver', 'cell_id': 'C150142',
                 'status': 'draft', 'borderline_excluded': [],
                 'relevant_laws': [{'law_id': law_id, 'quote': LAW['text'],
                                    'relevance_type': 'specific_match',
                                    'applies_to': ['motor_vehicle_driver'],
                                    'confidence': 'medium',
                                    'notes': 'Authored red curb and parking response are CPU probes; original paint, sign, service, activity and physical evidence require review.'}]}
    ref_batch = write('relevance_batch.json', relevance)
    ref_relevance = write('relevance.json', relevance)
    calls = [
        ('curb or road surface edge which is painted red',
         'Authored curb paint and map readback do not establish original visible paint or jurisdiction.',
         'red_curb_stop_or_park'),
        ('signage which indicates that parking is limited to tour buses, shuttle buses and limos',
         'Sign pixels, service class and lawful applicability need independent source review.',
         'signed_curb_observation'),
        ('signage which indicates that parking is limited to RTC buses',
         'RTC service identity and sign text need original source review.',
         'signed_curb_observation'),
        ('for a period up to thirty minutes for the loading or unloading of passengers',
         'The 1,800-second boundary and passenger activity require time-joined original sources.',
         'signed_curb_observation'),
        ('period necessary to conduct their business',
         'Necessary business duration cannot be inferred from a synthetic actor class or timer.',
         'business_activity_observation'),
        ('period of time necessary to expeditiously deposit mail',
         'Drop-box adjacency, actual deposit and expeditiousness require original observation.',
         'mail_deposit_observation'),
    ]
    judgments = [{'phrase': phrase, 'note': note} for phrase, note, _ in calls]
    template = {'actor': 'motor_vehicle_driver', 'law_id': law_id,
                'template_id': TEMPLATE_ID, 'quote': LAW['text'],
                'status': 'draft', 'parameter_refs': [],
                'structure': {'activation': {
                    'description': 'A vehicle stops, stands or parks beside a red-painted curb or road edge.',
                    'source_clause': 'Red indicates no stopping, standing or parking'},
                    'obligation': {'type': 'prohibition',
                        'description': 'No stopping, standing or parking at the red marking unless an exact stated exception applies.',
                        'source_clause': 'Red indicates no stopping, standing or parking'},
                    'exceptions': [
                        {'description': 'Signed tour bus, shuttle bus or limo loading or unloading within the stated duration.',
                         'source_clause': 'those vehicles may park for a period up to thirty minutes for the loading or unloading of passengers'},
                        {'description': 'Signed RTC bus loading or unloading within the stated duration.',
                         'source_clause': 'those vehicles may park for a period up to thirty minutes for the loading or unloading of passengers'},
                        {'description': 'Armored or emergency vehicle business for the necessary period regardless of sign.',
                         'source_clause': 'Armored cars and emergency vehicles may park at such locations for the period necessary to conduct their business'},
                        {'description': 'Adjacent U.S. mail drop box and expeditious deposit.',
                         'source_clause': 'a person may stop for the period of time necessary to expeditiously deposit mail in such a drop box'}],
                    'timing': {'description': 'Join original frames and time; signed passenger exceptions use the exact 1,800-second boundary, while necessary and expeditious remain source-reviewed judgments.'},
                    'judgment_calls_needed': judgments}}
    ref_template = write('template.json', template)
    refs = []
    for index, (phrase, note, output) in enumerate(calls):
        observed = {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
                    'status': 'draft', 'observable_requirements': {
                        'context_inputs': [{'name': 'red_curb_map_readback',
                                            'unit': 'structured',
                                            'description': 'Retain original map, curb, sign and service provenance.'}],
                        'observables': [{'name': 'red_curb_stop_or_park', 'unit': 'bool',
                                         'description': 'Time-joined Native observation for this clause; physical and legal interpretation pending.'}],
                        'recording_needs': [{'name': 'four_source_views', 'unit': 'video',
                                             'description': 'Retain source frames, actors, map readback and all four camera views.'}],
                        'landmarks': [], 'sweep_dimensions': [],
                        'limitations': [note, 'Synthetic diagnostics do not establish the original statutory fact.']}}
        refs.append(write(f'judgment_observables_{index}.json', observed))
    kinds = {'road_and_actors': 'world_setup', 'requested_parking_x_m': 'controller',
             'red_curb_stop_or_park': 'subject_behavior',
             'business_activity_request': 'controller', 'mail_deposit_request': 'controller',
             'mailbox_requested': 'world_setup', 'passenger_loading_request': 'controller',
             'requested_stationary_duration_s': 'controller',
             'service_class': 'world_setup', 'sign_classes': 'world_setup'}
    domains = {'road_and_actors': 'authored curb, sign and source-bound actor arrangement',
               'requested_parking_x_m': 'inside or outside authored red extent in meters',
               'red_curb_stop_or_park': 'source-observed stopped body relation to red paint',
               'business_activity_request': 'business actor activity requested or omitted',
               'mail_deposit_request': 'deposit actor activity requested or omitted',
               'mailbox_requested': 'adjacent mail drop box present or absent',
               'passenger_loading_request': 'loading event requested or omitted',
               'requested_stationary_duration_s': 'below, at or above 1,800 seconds where signed exception applies',
               'service_class': 'ordinary, tour, shuttle, limo, RTC, armored or emergency',
               'sign_classes': 'service restriction sign class or absent'}
    bindings = {'actor': 'motor_vehicle_driver', 'cell_id': 'C150142',
                'status': 'draft', 'context_refs': [], 'established_contexts': [],
                'fixed_parameters': [],
                'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
                'variable_parameters': [{'name': name, 'kind': kind,
                                         'range_or_domain': domains[name],
                                         'used_by_laws': [law_id]}
                                        for name, kind in kinds.items()]}
    ref_bindings = write('bindings.json', bindings)
    existing = json.loads((STAGE / 'cases.json').read_text())
    defaults = {name: {'kind': kind, 'value': None if kind == 'subject_behavior'
                        else 'not separately requested in this case'}
                for name, kind in kinds.items()}
    for case in existing['cases']:
        for name, value in defaults.items():
            case['variable_assignments'].setdefault(name, value)
        case['target_type'] = 'boundary_probe'
        case['paired_probe_id'] = 'red_curb_exception_matrix'
        case['deliberate_differences'] = [
            name for name in kinds if case['variable_assignments'][name] != defaults[name]]
        case['probe'] = {
            'primary_variable': 'requested_parking_x_m',
            'comparison_or_standard': 'Authored curb-zone and exception matrix; statutory judgment unresolved',
            'target_value_or_branch': case['case_id'].rsplit('__', 1)[-1],
        }
        case['unresolved_judgment_calls'] = [item['phrase'] for item in judgments]
    baseline = {'case_id': WORK.name + '__baseline', 'target_law_id': None,
                'target_type': 'baseline',
                'rationale': 'Shared red-curb source survey before each exact attempt.',
                'variable_assignments': defaults,
                'recording_description': existing['cases'][0]['recording_description'],
                'unresolved_judgment_calls': [item['phrase'] for item in judgments]}
    existing['cases'].insert(0, baseline)
    existing['sweep_specs'] = [{
        'sweep_id': 'red_curb_judgment_source_sweep',
        'target_law_id': law_id,
        'judgment_refs': judgments,
        'rationale': 'Original sign, service, passenger, business and mail observations are not available as source-bound physical sweep measurements.',
        'status': 'incomplete',
        'missing_inputs': ['Original Native source pixels and time-joined activities',
                           'Source-bound sweep measurement contract for each judgment'],
    }]
    ref_cases = write('canonical-cases.json', existing)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': WORK.name,
             'stages': {'relevance_batch': ref_batch, 'relevance': ref_relevance,
                        'template': ref_template, 'judgment_observables': refs,
                        'bindings': ref_bindings, 'cases': ref_cases}}
    write('semantic-index.json', index)


if __name__ == '__main__':
    main()
