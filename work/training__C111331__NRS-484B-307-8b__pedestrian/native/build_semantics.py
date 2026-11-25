"""Source-bound draft semantic stages for the frozen pedestrian assignment."""

import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent.parent
repo = folder.parents[1]
assignment = json.loads((repo / 'inputs' / folder.name / 'assignment.json').read_text())
plan = json.loads((folder / 'case-plan.json').read_text())
out = folder / 'proposals'


def write(name, data):
    path = out / (name + '.json')
    path.write_text(json.dumps(data, indent=2) + '\n')
    return {'path': 'proposals/' + path.name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


law = assignment['law']
text = law['text']
law_id, cell_id, actor = (assignment[k] for k in ('law_id', 'cell_id', 'actor'))
template_id = law_id + '@' + actor
relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
             'relevant_laws': [{'law_id': law_id, 'quote': text,
                                'applies_to': [actor], 'relevance_type': 'specific_match',
                                'confidence': 'medium',
                                'notes': 'Frozen pedestrian crossing cell; actual facing red and other-device indication require original review.'}],
             'borderline_excluded': []}
parameters = [
    {'name': 'steady_red_facing_pedestrian', 'kind': 'world_setup',
     'range_or_domain': 'authored red head and facing vector; physical governance pending'},
    {'name': 'other_device_permission', 'kind': 'world_setup',
     'range_or_domain': 'none, Walk, or flashing countdown request; statutory device authority pending'},
    {'name': 'pedestrian_highway_entry', 'kind': 'controller',
     'range_or_domain': 'stay outside or request entry; actual footprint measured after capture'},
]
template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
            'status': 'draft', 'quote': text,
            'structure': {
                'activation': {'condition': 'pedestrian faces a steady red signal alone',
                               'source_clause': 'Where the signal is a steady red signal alone:'},
                'obligation': {'type': 'must_not_enter',
                               'description': 'do not enter the highway while facing that signal',
                               'source_clause': 'Pedestrians facing such a signal shall not enter the highway'},
                'exceptions': [{'condition': 'another device permits proceeding under NRS 484B.283',
                                'source_clause': 'unless permitted to proceed by another device as provided in NRS 484B.283'}],
                'timing': {'description': 'measure the device indication and facing relation before first highway-footprint entry'},
                'judgment_calls_needed': []},
            'parameter_refs': parameters}
bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
            'established_contexts': [{'name': 'intersection_pedestrian_entry',
                                      'source': 'frozen assignment branch; original Native authority pending'}],
            'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
            'context_refs': [], 'fixed_parameters': [],
            'variable_parameters': [{**p, 'used_by_laws': [law_id]} for p in parameters]}
manifest = json.loads((folder / 'execution-manifest.json').read_text())
descriptions = {item['case_id']: json.loads(next(f['content'] for f in
                json.loads((folder / item['construction']).read_text())['files']
                if f['path'] == 'config.json'))['recording_description']
                for item in manifest['cases']}
configs = {item['case_id']: json.loads(next(f['content'] for f in
           json.loads((folder / item['construction']).read_text())['files']
           if f['path'] == 'config.json')) for item in manifest['cases']}
cases = {'format': 'worker-case-proposals', 'cell_id': cell_id, 'actor': actor,
         'status': 'draft', 'sweep_specs': [], 'cases': []}
cases['cases'].append({'case_id': folder.name + '__baseline',
                       'target_law_id': law_id, 'target_type': 'baseline',
                       'rationale': 'Shared authored intersection setup; no additional recording',
                       'fixed_context': 'Road, facing red head, four cameras and duration',
                       'variable_assignments': {}, 'unresolved_judgment_calls': [],
                       'recording_description': next(iter(descriptions.values()))})
for item in plan['cases']:
    cid = item['case_id']
    condition = cid.rsplit('__', 1)[-1]
    config = configs[cid]
    comparison = next(c for c in plan['comparisons'] if cid in c['case_ids'])
    primary = ('pedestrian_highway_entry' if condition in ('condition_a', 'condition_b')
               else 'other_device_permission')
    cases['cases'].append({'case_id': cid, 'target_law_id': law_id,
                           'target_type': 'compliant_attempt' if condition in
                           ('condition_a', 'exception_permits', 'exception_countdown') else 'violating_attempt',
                           'paired_probe_id': comparison['comparison_id'],
                           'deliberate_differences': [primary],
                           'probe': {'primary_variable': primary,
                                     'comparison_or_standard': comparison['comparison_id'],
                                     'target_value_or_branch': condition},
                           'rationale': 'Controlled ' + condition + ' pedestrian red-entry contrast',
                           'fixed_context': 'Hold road, steady-red head, cameras and duration fixed within each comparison.',
                           'variable_assignments': {
                               'steady_red_facing_pedestrian': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'authored steady red'},
                               'other_device_permission': {'kind': 'world_setup', 'unit': 'categorical', 'value': config['requested_other_device']},
                               'pedestrian_highway_entry': {'kind': 'controller', 'unit': 'bool', 'value': config['requested_entry']}},
                           'unresolved_judgment_calls': ['Native governance, display pixels and statutory device permission need original review'],
                           'recording_description': descriptions[cid]})
cases['cases'][0]['variable_assignments'] = cases['cases'][1]['variable_assignments']
stages = {'relevance_batch': write('relevance_batch', relevance),
          'relevance': write('relevance', relevance),
          'template': write('template', template),
          'judgment_observables': [],
          'bindings': write('bindings', bindings),
          'cases': write('cases', cases)}
write('semantic-index', {'format': 'worker-semantic-delivery',
                         'assignment_id': folder.name, 'stages': stages})
print(json.dumps({'case_proposals': len(cases['cases']), 'stages': list(stages)}))
