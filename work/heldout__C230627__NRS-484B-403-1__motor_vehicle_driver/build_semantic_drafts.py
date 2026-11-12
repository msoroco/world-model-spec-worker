"""Build source-bound, explicitly draft canonical semantic proposals for C230627."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parents[1] / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
P = ROOT / 'proposals'
IDENTITY = {'cell_id': 'C230627', 'actor': 'motor_vehicle_driver', 'status': 'draft'}
TEMPLATE = 'NRS-484B-403-1@motor_vehicle_driver'


def write(name, value):
    path = P / name
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relation = {'law_id': LAW['id'], 'quote': LAW['text'],
                'applies_to': ['motor_vehicle_driver'],
                'relevance_type': 'specific_match', 'confidence': 'high',
                'notes': 'Frozen road/u_turn/centerline cell; cited prohibitions require separate original context.'}
    relevance = dict(IDENTITY, relevant_laws=[relation], borderline_excluded=[])
    batch_ref = write('relevance_batch.json', relevance)
    relevance_ref = write('relevance.json', relevance)
    exceptions = [
        {'source_clause': 'except as prohibited by this section',
         'description': 'NRS 484B.403(2) and (3); source each applicable alternative separately'},
        {'source_clause': 'by the provisions of NRS 484B.227',
         'description': 'Divided-highway crossing restriction and its alternatives require original road geometry and authority context'},
        {'source_clause': '484B.363',
         'description': 'School-zone restriction and its time, child, sign or beacon context require original sources'},
        {'source_clause': '484B.407',
         'description': 'Curve/crest and 500 ft both-direction visibility require original geometry and body-ray sources'}]
    parameters = [
        ('u_turn_route', 'controller', 'Opposing lane target arc request'),
        ('oncoming_spawn_distance_m', 'world_setup', 'Engineering participant spawn request; no legal safety cutoff'),
        ('physical_safety', 'subject_behavior', 'Null pending original motion and independent judgment'),
        ('mapped_no_u_turn_device', 'world_setup', 'Mapped device candidate or null')]
    refs = [{'name': n, 'kind': k, 'range_or_domain': d} for n,k,d in parameters]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': 'motor_vehicle_driver',
                'status': 'draft', 'quote': LAW['text'],
                'structure': {'law_id': LAW['id'],
                              'activation': {'condition': 'A motor vehicle driver makes a U-turn on a road.', 'numeric_conditions': []},
                              'obligation': {'type': 'permission', 'description': 'A U-turn may be made where the whole turn can be made with safety, subject to cited prohibitions.', 'numeric_conditions': []},
                              'exceptions': exceptions,
                              'timing': {'description': 'Assess safety through the whole U-turn and cited prohibition context at the maneuver.', 'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': 'with safety', 'note': 'No numeric legal cutoff is supplied; original whole-maneuver motion, gaps, braking, sight and context need independent review.'}]},
                'parameter_refs': refs}
    template_ref = write('template.json', template)
    judgment = {'template_id': TEMPLATE, 'phrase': 'with safety',
                'note': 'No numeric legal cutoff is supplied; original whole-maneuver motion, gaps, braking, sight and context need independent review.', 'status': 'draft',
                'observable_requirements': {'observables': [
                    {'name': 'turn_heading_change_deg', 'unit': 'deg', 'description': 'Original yaw from onset through completion'},
                    {'name': 'minimum_participant_body_gap_m', 'unit': 'm', 'description': 'Sampled original body clearances over the maneuver'},
                    {'name': 'minimum_participant_acceleration_mps2', 'unit': 'm/s^2', 'description': 'Sampled original participant braking'}],
                    'context_inputs': [{'name': 'participant_roles', 'unit': 'structured context', 'description': 'Original Native actor identities and opposing/following lane role citation'}],
                    'sweep_dimensions': [{'name': 'oncoming_distance_m', 'unit': 'm', 'description': 'Engineering comparison request, 24 m versus 12 m'}],
                    'landmarks': [],
                    'recording_needs': [{'name': 'u_turn_observation', 'unit': 'structured', 'description': '20 Hz original ego and participant motion joined to frame identity'}],
                    'limitations': ['No measured clearance or acceleration alone resolves legal safety.', 'Synthetic diagnostic sources do not prove physical U-turn completion.']}}
    judgment_ref = write('judgment_with_safety.json', judgment)
    bindings = dict(IDENTITY, established_contexts=['road layout', 'U-turn maneuver', 'centerline control'],
                    law_refs=[{'template_id': TEMPLATE, 'binding_kind': 'direct'}], context_refs=[],
                    fixed_parameters=[{'name': 'cell_layout', 'value': 'road', 'rationale': 'Frozen catalog cell'},
                                      {'name': 'cell_maneuver', 'value': 'u_turn', 'rationale': 'Frozen catalog cell'},
                                      {'name': 'cell_control', 'value': 'centerline', 'rationale': 'Frozen catalog cell'}],
                    variable_parameters=[dict(ref, used_by_laws=[LAW['id']]) for ref in refs])
    bindings_ref = write('bindings.json', bindings)
    cases = json.loads((P / 'cases.json').read_text())
    import copy
    for case in cases['cases']:
        case['variable_assignments'].setdefault('mapped_no_u_turn_device',
            {'kind': 'world_setup', 'value': None})
        if case['target_type'] != 'baseline':
            if case['target_type'] == 'prohibition_context':
                case['target_type'] = 'boundary_probe'
            is_device = case['case_id'].endswith('__prohibition_403_2')
            axis = 'mapped_no_u_turn_device' if is_device else 'oncoming_spawn_distance_m'
            case['paired_probe_id'] = 'mapped_device_candidate' if is_device else 'safety_clearance'
            case['deliberate_differences'] = [axis]
            case['probe'] = {'primary_variable': axis,
                             'comparison_or_standard': 'Original U-turn source measurements and separately sourced cited prohibition context; no legal verdict from CPU fixtures',
                             'target_value_or_branch': case['variable_assignments'][axis]['value']}
    cases['sweep_specs'] = [{'sweep_id': 'whole_maneuver_safety_review',
                            'target_law_id': LAW['id'],
                            'judgment_refs': [{'phrase': 'with safety', 'note': judgment['note']}],
                            'status': 'incomplete',
                            'rationale': 'No numeric legal safety cutoff and no original physical U-turn recording exists.',
                            'missing_inputs': ['Original full-maneuver ego/participant motion and source context',
                                               'Independent safety judgment after local capture']}]
    cases['sweeps_expanded'] = True
    if not any(case['target_type'] == 'baseline' for case in cases['cases']):
        baseline = copy.deepcopy(cases['cases'][0])
        baseline['case_id'] = ROOT.name + '__semantic_baseline'
        baseline['target_type'] = 'baseline'
        baseline['rationale'] = 'Shared centerline U-turn semantic baseline; no separate recording request.'
        cases['cases'].insert(0, baseline)
    write('cases.json', cases)
    cases_ref = {'path': 'proposals/cases.json', 'sha256': hashlib.sha256((P/'cases.json').read_bytes()).hexdigest()}
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ROOT.name,
             'stages': {'relevance_batch': batch_ref, 'relevance': relevance_ref,
                        'template': template_ref, 'judgment_observables': [judgment_ref],
                        'bindings': bindings_ref, 'cases': cases_ref},
             'status': 'draft_incomplete_cases',
             'limitations': ['Case stage currently contains only three constructed cases; remaining cited prohibition cases require construction and exact proofs.']}
    write('semantic-index.json', index)
    print('draft semantic stages written; cases:', len(cases['cases']))


if __name__ == '__main__':
    main()
