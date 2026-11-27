"""Build source-faithful private-way highway entry semantic proposals."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
TEMPLATE = LAW['id'] + '@' + ASSIGNMENT['actor']
CASES = [ROOT.name + '__probe_a', ROOT.name + '__probe_b']


def put(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False).rstrip() + '\n')
    return {'path': path.relative_to(ROOT).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    relevance = {'cell_id': 'C177626', 'actor': ASSIGNMENT['actor'], 'status': 'draft',
        'relevant_laws': [{'law_id': LAW['id'], 'quote': LAW['text'],
            'applies_to': [ASSIGNMENT['actor']], 'relevance_type': 'direct',
            'confidence': 'high',
            'notes': 'Private-way approach and entry to paved highway with two inventoried approaching highway vehicles.'}],
        'borderline_excluded': []}
    r1 = put('relevance_batch.json', relevance)
    r2 = put('relevance.json', relevance)
    judgment = {'phrase': 'yield the right-of-way to all vehicles approaching on such highway',
                'note': 'Every approaching vehicle must be inventoried; conflict order, occupancy and speed response are observations, not legal thresholds.'}
    params = [
        {'name': 'ego_release_frame', 'kind': 'controller', 'range_or_domain': [30, 250]},
        {'name': 'highway_vehicle_speed_mps', 'kind': 'controller', 'range_or_domain': [8]},
        {'name': 'private_way_geometry', 'kind': 'world_setup',
         'range_or_domain': ['private way terminates at two-way paved highway']},
        {'name': 'approaching_vehicle_count', 'kind': 'world_setup', 'range_or_domain': [2]},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW['id'], 'actor': ASSIGNMENT['actor'],
        'quote': LAW['text'], 'status': 'draft',
        'structure': {'law_id': LAW['id'],
            'activation': {'condition': 'Driver of a vehicle is about to enter or cross a highway from a private way, with vehicles approaching on that highway.',
                           'numeric_conditions': []},
            'obligation': {'type': 'must_yield',
                           'description': 'Yield right-of-way to all vehicles approaching on the highway.',
                           'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Measure original private-way approach, highway entry, all approaching vehicle arrivals and continuous roadway occupancy.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [judgment]},
        'parameter_refs': params}
    r3 = put('template.json', template)
    r4 = put('judgment-observables-1.json', {'template_id': TEMPLATE,
        'phrase': judgment['phrase'], 'note': judgment['note'], 'status': 'draft',
        'observable_requirements': {'observables': [
            {'name': term['term'], 'unit': 'structured',
             'description': 'Original private-way/highway geometry, all actor bodies and frame joined road traffic'}
            for term in ASSIGNMENT['source_observation_terms']],
            'context_inputs': [{'name': 'private_way_and_highway', 'unit': 'source context',
                                'description': 'Original private way and highway identity and topology'}],
            'sweep_dimensions': [], 'landmarks': [],
            'recording_needs': [{'name': 'drv.approaching', 'unit': 'structured',
                'description': 'Every original highway actor body, velocity, entry and conflict sequence plus four-view pixels.'}],
            'limitations': [judgment['note'],
                'Original Native motion, complete external traffic inventory, pixels and right-of-way judgment require independent review.']}})
    binding = {'cell_id': 'C177626', 'actor': ASSIGNMENT['actor'], 'status': 'draft',
        'established_contexts': [],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(param, used_by_laws=[LAW['id']]) for param in params]}
    r5 = put('bindings.json', binding)
    recording = json.loads((ROOT / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': ROOT.name + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'rationale': 'Unselected private-way/highway source context.',
        'variable_assignments': {p['name']: {'kind': p['kind'], 'value': None,
                                             'unit': 'categorical'} for p in params},
        'unresolved_judgment_calls': [], 'recording_description': recording}]
    for rank, (case_id, release, action) in enumerate(zip(CASES, (250, 30),
        ('yield until all highway vehicles pass', 'enter between approach arrivals')), 1):
        cases.append({'case_id': case_id, 'target_law_id': LAW['id'],
            'target_type': 'judgment_sweep',
            'rationale': 'Original all-vehicle inventory and full-body entry order comparison; legal judgment separate.',
            'variable_assignments': {
                'ego_release_frame': {'kind': 'controller', 'value': release, 'unit': 'frame'},
                'highway_vehicle_speed_mps': {'kind': 'controller', 'value': 8, 'unit': 'm/s'},
                'private_way_geometry': {'kind': 'world_setup',
                    'value': 'private way terminates at two-way paved highway', 'unit': 'categorical'},
                'approaching_vehicle_count': {'kind': 'world_setup', 'value': 2, 'unit': 'count'}},
            'unresolved_judgment_calls': [judgment['phrase']],
            'paired_probe_id': ROOT.name + '__comparison',
            'deliberate_differences': ['ego_release_frame'],
            'probe': {'primary_variable': 'ego_release_frame',
                      'comparison_or_standard': 'Original full-body entry versus all highway arrivals',
                      'target_value_or_branch': action},
            'recording_description': recording, 'selection_rank': rank})
    r6 = put('cases.json', {'cell_id': 'C177626', 'actor': ASSIGNMENT['actor'],
        'status': 'draft', 'sweep_specs': [{
            'sweep_id': ROOT.name + '__comparison',
            'target_law_id': LAW['id'], 'status': 'incomplete',
            'judgment_refs': [judgment],
            'rationale': 'Controlled source-bound all-approaching-vehicle entry comparison.',
            'missing_inputs': ['Original Native physical capture and independent review.']}],
        'sweeps_expanded': True, 'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name,
        'stages': {'relevance_batch': r1, 'relevance': r2, 'template': r3,
                   'judgment_observables': [r4], 'bindings': r5, 'cases': r6}})
    print('Private-way semantic proposals written')


if __name__ == '__main__':
    main()
