"""Author draft semantic stages for the fixed aid/contest branch."""
import hashlib
import json
from pathlib import Path

from package_spec import AID, LAW, RECORDING

HERE = Path(__file__).resolve().parent
OUT = HERE / 'proposals'


def put(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assign(value):
    return {'kind': 'world_setup', 'value': value, 'unit': 'source request'}


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if plan['assignment_id'] != AID or len(plan['cases']) != 4:
        raise ValueError('four exact aid/contest cases required')
    law, actor, quote = plan['law_id'], plan['actor'], plan['law_text']
    relevance = {'cell_id': plan['cell_id'], 'actor': actor, 'status': 'draft',
        'relevant_laws': [{'law_id': law, 'quote': quote, 'applies_to': [actor],
                           'confidence': 'high'}], 'borderline_excluded': []}
    relevance_ref = put('relevance.json', relevance)
    put('relevance-batch.json', relevance)
    template_id = law + '@' + actor
    parameters = [
        {'name': 'cue_conduct', 'kind': 'world_setup', 'range_or_domain': 'present or absent',
         'unit': 'source request'},
        {'name': 'candidate_contest_episode', 'kind': 'world_setup',
         'range_or_domain': 'present or absent', 'unit': 'source request'},
        {'name': 'highway_status', 'kind': 'world_setup',
         'range_or_domain': 'source established or absent', 'unit': 'source request'}]
    judgment = [
        {'phrase': 'motor vehicle speed contest',
         'note': 'Other motorist motion and coordinated timing do not themselves define a legal contest.'},
        {'phrase': 'aid or abet',
         'note': 'A physical start cue and temporal ordering do not themselves decide legal assistance or intent.'}]
    template_ref = put('template.json', {'template_id': template_id,
        'law_id': law, 'actor': actor, 'status': 'draft', 'quote': quote,
        'structure': {'law_id': law,
            'activation': {'condition': 'A person and another motorist on a highway.',
                           'numeric_conditions': []},
            'obligation': {'description': 'No person shall aid or abet a motor vehicle speed contest upon a highway.',
                           'type': 'must_not', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Original cue relative to another motorist start and full episode.',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgment},
        'parameter_refs': parameters})
    obs_refs = []
    for item in judgment:
        name = 'judgment-' + ('contest' if item['phrase'].startswith('motor') else 'aid-abet') + '.json'
        obs_refs.append(put(name, {'template_id': template_id,
            'phrase': item['phrase'], 'note': item['note'], 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': ch['name'], 'unit': ch['unit'],
                                 'description': ch['method']}
                                for ch in RECORDING['channels']],
                'context_inputs': [{'name': 'reviewed_native_site', 'unit': 'source record',
                                    'description': 'Sealed highway, participant and episode sources'}],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': ch['name'], 'unit': ch['unit'],
                                     'description': ch['method']}
                                    for ch in RECORDING['channels']],
                'limitations': ['No numeric legal cutoff is inferred from cue or motion.']}}))
    bindings_ref = put('bindings.json', {'cell_id': plan['cell_id'], 'actor': actor,
        'status': 'draft', 'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(p, used_by_laws=[law]) for p in parameters]})
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'status': 'draft',
        'rationale': 'Common two-person/two-vehicle route and Native source context; no accepted recording.',
        'variable_assignments': {'cue_conduct': assign('present'),
                                 'candidate_contest_episode': assign('present'),
                                 'highway_status': assign('source established')},
        'unresolved_judgment_calls': [j['phrase'] for j in judgment],
        'recording_description': RECORDING}
    cases = [baseline]
    for item in plan['cases']:
        suffix = item['case_id'].removeprefix(AID + '__')
        dimensions = {
            'cue_conduct': 'absent' if suffix.startswith('no_cue') else 'present',
            'candidate_contest_episode': 'absent' if suffix.endswith('no_contest') else 'present',
            'highway_status': 'absent' if suffix.endswith('off_highway') else 'source established'}
        cases.append({'case_id': item['case_id'], 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': 'Original source-joined cue, episode and highway comparison; legal meanings unresolved.',
            'paired_probe_id': suffix,
            'deliberate_differences': [key for key, value in dimensions.items()
                                      if value not in ('present', 'source established')],
            'variable_assignments': {key: assign(value) for key, value in dimensions.items()},
            'unresolved_judgment_calls': [j['phrase'] for j in judgment],
            'recording_description': RECORDING,
            'probe': {'primary_variable': next((key for key, value in dimensions.items()
                                                 if value not in ('present', 'source established')),
                                                'cue_conduct'),
                      'comparison_or_standard': 'same identified participants, vehicles, route, lane and source format',
                      'target_value_or_branch': suffix}})
    cases_ref = put('cases.json', {'cell_id': plan['cell_id'], 'actor': actor,
        'status': 'draft', 'sweep_specs': [
            {'sweep_id': 'contest-aid-judgment-review', 'target_law_id': law,
             'judgment_refs': judgment, 'status': 'incomplete',
             'rationale': 'Physical observations cannot bound legal contest, aid or abet.',
             'missing_inputs': ['Original episode and independent legal review']}],
        'sweeps_expanded': True, 'cases': cases})
    put('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': obs_refs,
                   'bindings': bindings_ref, 'cases': cases_ref},
        'status': 'source_gated_draft'})
    return len(cases) - 1


if __name__ == '__main__':
    print('aid/contest semantic cases:', build())
