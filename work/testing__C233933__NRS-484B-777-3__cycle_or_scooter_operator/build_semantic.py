"""Select four source-grounded rider formation cases and stage semantics."""
import hashlib
import json
from pathlib import Path
from abreast import CASES
from package_spec import AID, LAW, RECORDING

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'

def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def assign(value):
    return {'kind': 'world_setup', 'value': value, 'unit': 'source request'}

def build():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    if plan['assignment_id'] != AID or len(plan['cases']) != 4 or len(plan['comparisons']) != 3:
        raise ValueError('four exact rider cases and three comparisons required')
    identities = {AID + '__' + case.name: case for case in CASES}
    ids = [row['case_id'] for row in plan['cases']]
    if set(ids) != set(identities):
        raise ValueError('exact rider cases differ')
    for row in plan['cases']:
        case = identities[row['case_id']]
        row.update({'kind': 'delivery', 'new_capture_selected': True,
                    'gap_ids': ['unverified-law-coverage'], 'target_law_id': LAW,
                    'requested_rider_count': case.riders,
                    'requested_exclusive_use': case.exclusive,
                    'requested_roadway_occupancy': case.roadway,
                    'construction_status': 'source_gated_native_bundle_cpu_preparation',
                    'required_original_packets': ['frame_map', 'separate_rider_identities',
                                                  'bicycle_classification', 'surface_designation',
                                                  'formation_positions', 'four_camera_video'],
                    'candidate_risk': {'status': 'physical', 'reason': row['physical_risk']}})
    differences = ['rider_count', 'exclusive_use_designation', 'occupied_surface_kind']
    for index, comparison in enumerate(plan['comparisons']):
        comparison['comparison_id'] = ('rider_count', 'exclusive_roadway', 'exclusive_path')[index]
        comparison['deliberate_differences'] = [differences[index]]
        comparison['fixed_conditions'] = [comparison['fixed_conditions']]
        comparison['status'] = 'planned_source_gated'
    plan['selected_branch'] = plan['selected_branches'][0]['branch']
    plan['observations'] = [{'name': item['name'], 'method': item['method'],
                             'source': 'original Native three-rider capture plus independently designated surface and bicycle packet'}
                            for item in RECORDING['channels']]
    source = 'inputs/' + AID + '/assignment.json'
    plan['requirement_dispositions'] = [
        {'disposition_index': 0, 'requirement': 'persons riding qualifying bicycles on roadway or exclusive path',
         'source': source, 'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'individual Native bicycle identities and independently sourced roadway/path classification'},
        {'disposition_index': 1, 'requirement': 'more than two abreast versus two abreast',
         'source': source, 'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'original 20 Hz rider geometry; 0.25 m physical tolerance only'},
        {'disposition_index': 2, 'requirement': 'exclusive-use path or roadway exception',
         'source': source, 'status': 'selected_required', 'case_ids': ids,
         'evidence_or_gap': 'independent exclusive-use designation or its absence, separate from occupancy'}]
    plan['source_observation_mapping'] = {}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 45,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'view': name, 'subject': 'all riders, formation and occupied roadway or path',
                                         'interval': 'first through final original frame'}
                                        for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
                           'limitation': 'No invented legal abreast cutoff or moped inclusion'}
    plan['planning_status'] = 'four_selected_rider_cases_source_gated_cpu_preparation'
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    quote = plan['law_text']
    relevance = {'cell_id': plan['cell_id'], 'actor': plan['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote, 'applies_to': [plan['actor']],
                                    'confidence': 'high'}], 'borderline_excluded': []}
    relevance_ref = put('relevance.json', relevance)
    put('relevance-batch.json', relevance)
    template_id = LAW + '@' + plan['actor']
    parameters = [
        {'name': 'rider_count', 'kind': 'world_setup', 'range_or_domain': 'two or three separate bicycle riders', 'unit': 'source request'},
        {'name': 'exclusive_use_designation', 'kind': 'world_setup', 'range_or_domain': 'officially designated or not designated', 'unit': 'source request'},
        {'name': 'occupied_surface_kind', 'kind': 'world_setup', 'range_or_domain': 'roadway or exclusive-use path', 'unit': 'source request'}]
    template_ref = put('template.json', {'template_id': template_id, 'law_id': LAW,
        'actor': plan['actor'], 'status': 'draft', 'quote': quote,
        'structure': {'law_id': LAW,
            'activation': {'condition': 'Qualifying bicycle, electric bicycle or electric scooter riders occupy a roadway.', 'numeric_conditions': []},
            'obligation': {'description': 'Do not ride more than two abreast on roadway outside the exclusive-use exception.', 'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [{'source_clause': 'except on paths or parts of roadways set aside for the exclusive use of bicycles, electric bicycles and electric scooters.',
                            'description': 'Source-designated exclusive-use paths or parts of roadways.',
                            'numeric_conditions': []}],
            'timing': {'description': 'Measure continuous rider arrangement from original frames; preserve legal abreast interpretation.', 'numeric_conditions': []},
            'judgment_calls_needed': []}, 'parameter_refs': parameters})
    bindings_ref = put('bindings.json', {'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'status': 'draft', 'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in parameters]})
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
                'status': 'draft', 'rationale': 'Common source-reviewed highway, bicycles and individual riders; no accepted recording or legal verdict.',
                'variable_assignments': {'rider_count': assign(2), 'exclusive_use_designation': assign(False),
                                         'occupied_surface_kind': assign('roadway')},
                'unresolved_judgment_calls': ['Legal abreast and exclusive-use interpretation require independent review'],
                'recording_description': RECORDING}
    selected = [baseline]
    for row in plan['cases']:
        case = identities[row['case_id']]
        selected.append({'case_id': row['case_id'], 'target_law_id': LAW,
            'target_type': 'violating_attempt' if case.riders == 3 and not case.exclusive else 'compliant_attempt',
            'status': 'draft', 'rationale': 'Original rider count and formation separated from designated surface; legal judgments unresolved.',
            'paired_probe_id': 'rider-formation-and-exclusive-use',
            'deliberate_differences': differences,
            'variable_assignments': {'rider_count': assign(case.riders),
                                     'exclusive_use_designation': assign(case.exclusive),
                                     'occupied_surface_kind': assign('roadway' if case.roadway else 'path')},
            'unresolved_judgment_calls': ['Legal abreast and exclusive-use interpretation require independent review'],
            'recording_description': RECORDING,
            'probe': {'primary_variable': 'rider_count' if case.riders == 2 else 'exclusive_use_designation',
                      'comparison_or_standard': 'same rider blueprint, source highway, cameras and duration except stated rider/surface difference',
                      'target_value_or_branch': case.name}})
    cases_ref = put('cases.json', {'cell_id': plan['cell_id'], 'actor': plan['actor'],
        'status': 'draft', 'sweep_specs': [], 'sweeps_expanded': True, 'cases': selected})
    put('semantic-index.json', {'format': 'worker-semantic-delivery', 'assignment_id': AID,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': [],
                   'bindings': bindings_ref, 'cases': cases_ref}, 'status': 'source_gated_draft'})
    return len(plan['cases'])

if __name__ == '__main__':
    print('rider formation semantic cases:', build())
