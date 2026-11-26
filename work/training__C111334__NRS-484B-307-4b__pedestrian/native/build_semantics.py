"""Build source-bound draft semantic stages for the exact arrow-only rule."""

import hashlib
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
OUT = FOLDER / 'proposals'


def load(path):
    return json.loads(path.read_text())


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = load(REPO / 'inputs' / FOLDER.name / 'assignment.json')
    plan = load(FOLDER / 'case-plan.json')
    law = assignment['law']
    law_id, cell_id, actor = (assignment[k] for k in ('law_id', 'cell_id', 'actor'))
    template_id = law_id + '@' + actor
    relevance = {
        'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law_id, 'quote': law['text'],
                           'applies_to': [actor], 'relevance_type': 'specific_match',
                           'confidence': 'medium',
                           'notes': 'Frozen intersection pedestrian crossing; original arrow display, facing and permission authority need review.'}],
        'borderline_excluded': []}
    parameters = [
        {'name': 'green_turn_arrow_alone_facing_pedestrian', 'kind': 'world_setup',
         'range_or_domain': 'authored arrow-only head; original facing and pixels pending'},
        {'name': 'other_device_permission', 'kind': 'world_setup',
         'range_or_domain': 'none or authored permission request; authority under NRS 484B.283 pending'},
        {'name': 'pedestrian_highway_entry', 'kind': 'controller',
         'range_or_domain': 'stay outside or request same crossing trajectory; footprint measured after capture'},
    ]
    template = {
        'template_id': template_id, 'law_id': law_id, 'actor': actor,
        'status': 'draft', 'quote': law['text'],
        'structure': {
            'activation': {'condition': 'green turn arrow alone faces the pedestrian',
                           'source_clause': 'Where the signal is a green turn arrow alone:'},
            'obligation': {'type': 'must_not_enter',
                           'description': 'do not enter the highway until permitted by another device',
                           'source_clause': 'Pedestrians facing such a signal shall not enter the highway until permitted to proceed by another device'},
            'exceptions': [{'condition': 'another device permits proceeding under NRS 484B.283',
                            'source_clause': 'as provided in NRS 484B.283'}],
            'timing': {'description': 'compare independently reviewed device indication and permission at first highway-footprint occupancy'},
            'judgment_calls_needed': []},
        'parameter_refs': parameters}
    bindings = {
        'cell_id': cell_id, 'actor': actor, 'status': 'draft',
        'established_contexts': [{'name': 'intersection_pedestrian_entry',
                                  'source': 'frozen C111334 assignment and exact Native construction; physical device authority pending'}],
        'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{**p, 'used_by_laws': [law_id]} for p in parameters]}
    constructions = {}
    configs = {}
    for item in plan['cases']:
        cid = item['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        construction = load(FOLDER / 'native-selected' / suffix / 'construction.json')
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        constructions[cid] = construction
        configs[cid] = config
    cases = {'format': 'worker-case-proposals', 'cell_id': cell_id,
             'actor': actor, 'status': 'draft', 'sweep_specs': [], 'cases': []}
    first = next(iter(constructions.values()))['recording_description']
    cases['cases'].append({
        'case_id': FOLDER.name + '__baseline', 'target_law_id': law_id,
        'target_type': 'baseline',
        'rationale': 'Shared authored crossing and device context; no additional recording',
        'fixed_context': 'Same highway boundary, facing arrow request, four cameras and duration',
        'variable_assignments': {}, 'unresolved_judgment_calls': [],
        'recording_description': first})
    for item in plan['cases']:
        cid = item['case_id']
        suffix = cid.rsplit('__', 1)[-1]
        comparison = next(c for c in plan['comparisons'] if cid in c['case_ids'])
        primary = ('other_device_permission' if suffix == 'permission_before_entry'
                   else 'pedestrian_highway_entry')
        variables = {
            'green_turn_arrow_alone_facing_pedestrian': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'authored arrow-only request'},
            'other_device_permission': {'kind': 'world_setup', 'unit': 'bool', 'value': suffix == 'permission_before_entry'},
            'pedestrian_highway_entry': {'kind': 'controller', 'unit': 'bool', 'value': suffix != 'probe_1'},
        }
        cases['cases'].append({
            'case_id': cid, 'target_law_id': law_id,
            'target_type': 'compliant_attempt' if suffix != 'probe_2' else 'violating_attempt',
            'paired_probe_id': comparison['comparison_id'],
            'deliberate_differences': [primary],
            'probe': {'primary_variable': primary,
                      'comparison_or_standard': comparison['comparison_id'],
                      'target_value_or_branch': suffix},
            'rationale': 'Controlled arrow-only pedestrian entry and other-device permission comparison',
            'fixed_context': 'Hold road, arrow request, cameras and duration fixed within each comparison',
            'variable_assignments': variables,
            'unresolved_judgment_calls': ['Original arrow display, facing, device authority and physical entry need local review'],
            'recording_description': constructions[cid]['recording_description']})
    cases['cases'][0]['variable_assignments'] = cases['cases'][1]['variable_assignments']
    stages = {
        'relevance_batch': write('relevance_batch', relevance),
        'relevance': write('relevance', relevance),
        'template': write('template', template),
        'judgment_observables': [],
        'bindings': write('bindings', bindings),
        'cases': write('cases', cases),
    }
    write('semantic-index', {'format': 'worker-semantic-delivery',
                             'assignment_id': FOLDER.name, 'stages': stages})
    return {'cases': len(cases['cases']), 'stages': list(stages)}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
