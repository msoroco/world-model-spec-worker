"""Build source-bound canonical semantic proposals for partition 4."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BATCH = json.loads((ROOT / 'batch.json').read_text())

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')

def ref(folder, name, value):
    path = folder / 'proposals' / (name + '.json')
    put(path, value)
    return {'path': 'proposals/' + name + '.json', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

def create(aid):
    folder = ROOT / 'work' / aid
    source = ROOT / 'inputs' / aid / 'assignment.json'
    if not source.exists(): source = folder / 'assignment.json'
    assignment = json.loads(source.read_text())
    plan = json.loads((folder / 'case-plan.json').read_text())
    original = json.loads((folder / 'proposals/cases.json').read_text())
    law, cell, actor = assignment['law_id'], assignment['cell_id'], assignment['actor']
    text, summary = assignment['law']['text'], assignment['summary']
    relevance = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law, 'quote': text, 'applies_to': [actor],
                                    'relevance_type': 'direct', 'confidence': 'high',
                                    'notes': 'Selected source-backed testing assignment'}],
                 'borderline_excluded': []}
    cases = [copy.deepcopy(case) for case in original['cases'] if case['target_type'] != 'baseline']
    all_vars = {}
    for case in cases:
        for name, value in case['variable_assignments'].items():
            all_vars.setdefault(name, value)
    parameters = [{'name': name, 'kind': value['kind'],
                   'range_or_domain': 'Exact authored branch values; physical realization unverified'}
                  for name, value in sorted(all_vars.items())]
    phrases = sorted({phrase for case in cases for phrase in case.get('unresolved_judgment_calls', [])})
    if law.endswith('400-2b'):
        phrases = ['Departure to the right of the entered highway centerline and highway status']
    judgments = [{'phrase': phrase, 'note': 'Original physical evidence required; legal interpretation deferred'}
                 for phrase in phrases]
    exceptions = []
    for item in summary.get('exceptions', []):
        clause = 'but such driver, having so yielded and having given a signal when and as required, may make such left turn'
        exceptions.append({'trigger': item, 'effect': 'Source-conditioned alternative duty',
                           'replacement_obligation': item,
                           'source_clause': clause if clause in text else text})
    template = {'template_id': law + '@' + actor, 'law_id': law, 'actor': actor,
                'quote': text,
                'structure': {'law_id': law,
                              'activation': {'condition': '; '.join(summary.get('activation_conditions', [])),
                                             'numeric_conditions': []},
                              'obligation': {'description': text, 'type': 'must',
                                             'numeric_conditions': []},
                              'exceptions': exceptions,
                              'timing': {'description': '; '.join(x['requirement'] for x in summary.get('timing_requirements', [])),
                                         'numeric_conditions': []},
                              'judgment_calls_needed': judgments},
                'parameter_refs': parameters}
    obs_refs = []
    channels = cases[0]['recording_description']['channels']
    for index, judgment in enumerate(judgments):
        items = [{'name': c['name'], 'unit': c['unit'], 'description': c['method']} for c in channels]
        obs = {'template_id': template['template_id'], 'phrase': judgment['phrase'],
               'note': judgment['note'], 'status': 'draft',
               'observable_requirements': {'observables': items, 'context_inputs': [],
                   'sweep_dimensions': [], 'landmarks': [], 'recording_needs': items,
                   'limitations': ['Native motion and pixels require local GPU execution; legal judgment is unresolved.']}}
        obs_refs.append(ref(folder, 'judgment-' + str(index), obs))
    binding = {'cell_id': cell, 'actor': actor, 'status': 'draft',
               'established_contexts': [],
               'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [dict(p, used_by_laws=[law]) for p in parameters]}
    by_id = {case['case_id']: case for case in cases}
    membership = {}
    for comparison in plan['comparisons']:
        members = [by_id[cid] for cid in comparison['case_ids']]
        differing = sorted(name for name in all_vars if
                           len({json.dumps(item['variable_assignments'].get(name), sort_keys=True)
                                for item in members}) > 1)
        if not differing:
            differing = [next(iter(all_vars))]
        for cid in comparison['case_ids']:
            membership.setdefault(cid, (comparison['comparison_id'], differing))
    for case in cases:
        pair, differences = membership.get(case['case_id'],
                                           (case['case_id'].split('__')[-1], [next(iter(all_vars))]))
        case['paired_probe_id'] = pair
        case['deliberate_differences'] = differences
        case['probe'] = {'primary_variable': differences[0],
                         'comparison_or_standard': 'Controlled physical branch comparison; legal judgment unresolved',
                         'target_value_or_branch': case['case_id'].split('__')[-1]}
        if law.endswith('400-2b'):
            case['unresolved_judgment_calls'] = [judgments[0]['phrase']]
    baseline = copy.deepcopy(cases[0])
    baseline.update(case_id=aid + '__neutral_baseline', target_law_id=None,
                    target_type='baseline', rationale='Neutral reference definition; not selected for capture',
                    unresolved_judgment_calls=[])
    for field in ('paired_probe_id', 'deliberate_differences', 'probe'):
        baseline.pop(field, None)
    sweep_specs = [{'sweep_id': 'judgment-' + str(index), 'target_law_id': law,
                    'judgment_refs': [judgment], 'status': 'incomplete',
                    'rationale': 'Existing v7 branch comparisons preserve exact identities; no legal cutoff is authored.',
                    'missing_inputs': ['A source-backed scalar physical sweep design for this qualitative judgment is unavailable.']}
                   for index, judgment in enumerate(judgments)]
    canonical = {'cell_id': cell, 'actor': actor, 'status': 'draft',
                 'cases': [baseline] + cases, 'sweep_specs': sweep_specs}
    # Statutory speed conditions bind to observed speed. Controller speed is
    # an engineering setpoint; local Native traces must establish the result.
    if law in ('NRS-484B-600-1e', 'NRS-484B-600-1c'):
        actual = {'name': 'ego_speed', 'kind': 'subject_behavior',
                  'range_or_domain': 'Observed original Native speed, not a commanded target',
                  'used_by_laws': [law]}
        if not any(v['name'] == actual['name'] for v in binding['variable_parameters']):
            binding['variable_parameters'].append(actual)
            template['parameter_refs'].append({k: actual[k] for k in ('name','kind','range_or_domain')})
        for case in canonical['cases']:
            case['variable_assignments']['ego_speed'] = {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s'}
        if law.endswith('600-1e'):
            bound = 35.7632  # Exact conversion of the source's 80 mph.
        else:
            bound = 'posted_speed_mps'
            posted = {'name': 'posted_speed_mps', 'kind': 'world_setup',
                      'range_or_domain': 'Authority-posted limit on the traversed portion',
                      'used_by_laws': [law]}
            if not any(v['name'] == posted['name'] for v in binding['variable_parameters']):
                binding['variable_parameters'].append(posted)
                template['parameter_refs'].append({k: posted[k] for k in ('name','kind','range_or_domain')})
            for case in canonical['cases']:
                case['variable_assignments']['posted_speed_mps'] = {'kind': 'world_setup', 'value': 13.4112, 'unit': 'm/s'}
        template['structure']['obligation']['numeric_conditions'] = [
            {'variable': 'ego_speed', 'operator': '>', 'value': bound, 'unit': 'm/s'}]
        for case in canonical['cases']:
            if case['target_type'] != 'baseline':
                suffix = case['case_id'].split('__')[-1]
                if suffix in ('below', 'equal', 'above'):
                    case['probe'].update(primary_variable='ego_speed',
                        threshold_ref='obligation.numeric_conditions[0]',
                        operator='>', unit='m/s',
                        test_value=case['variable_assignments']['requested_speed_mps']['value'])
                    case['epsilon_used'] = {'value': 0.44704, 'unit': 'm/s',
                        'rationale': 'One-mph engineering probe step; no legal tolerance.'}
    refs = {'relevance_batch': ref(folder, 'relevance_batch', relevance),
            'relevance': ref(folder, 'relevance', relevance),
            'template': ref(folder, 'template', template),
            'judgment_observables': obs_refs,
            'bindings': ref(folder, 'bindings', binding),
            'cases': ref(folder, 'cases', canonical)}
    put(folder / 'proposals/semantic-index.json',
        {'format': 'worker-semantic-delivery-v1', 'assignment_id': aid, 'stages': refs})

if __name__ == '__main__':
    ids = [aid for aid, info in BATCH['assignments'].items() if info['partition'] == 4]
    coverage = json.loads((ROOT / 'work/_shared/branch-coverage.json').read_text())
    ids += [row['assignment_id'] for row in coverage['additional_bindings']
            if row['original_assignment_id'] in ids]
    for assignment_id in ids:
        create(assignment_id)
