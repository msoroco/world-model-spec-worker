"""Build source-faithful sidewalk overtake semantic draft and open sweeps."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'LVMC-11-40-180-C'
ACTOR = 'cycle_or_scooter_operator'
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C142510', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('yield the right-of-way to any pedestrian',
         'Original trajectories, full body separation and pedestrian response need independent review.',
         'sidewalk_body_history'),
        ('give audible signal',
         'Original rider emitter event and pedestrian microphone waveform need independent physical and human audibility review.',
         'pedestrian_audio')]
    parameters = [
        {'name': 'rider_kind', 'kind': 'world_setup',
         'range_or_domain': 'bicycle, electric bicycle, electric scooter', 'unit': 'category'},
        {'name': 'signal_timing', 'kind': 'world_setup',
         'range_or_domain': 'before pass, after pass, or silent', 'unit': 'category'},
        {'name': 'rider_response', 'kind': 'world_setup',
         'range_or_domain': 'brake before pass or advance', 'unit': 'category'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'A person rides a bicycle, electric bicycle, or electric scooter upon a sidewalk and overtakes and passes a pedestrian.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Yield the right-of-way to the pedestrian and give audible signal before overtaking and passing.',
                                   'type': 'must', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Observe signal relative to actual original passing and yielding behavior through the approach.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgments]},
                'parameter_refs': parameters}
    template_ref = write('template.json', template)
    judgment_refs = []
    for number, (phrase, note, channel) in enumerate(judgments):
        judgment_refs.append(write(f'judgment-{number}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'source observation', 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'm' if channel == 'sidewalk_body_history' else 'synthetic emission event',
                                     'description': note}],
                'limitations': ['Physical and legal judgment requires original reviewed connected sidewalk and audible source.']}}))
    binding_ref = write('bindings.json', {
        'cell_id': 'C142510', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in parameters]})
    cases = []
    for case in plan['cases']:
        cid = case['case_id']
        name = cid.removeprefix(AID + '__')
        construction = json.loads((HERE / ('construction-compatibility-' + name + '.json')).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        signal = config['case']['signal_frame']
        primary = 'rider_kind' if name.startswith('electric_') else ('rider_response' if name.endswith('advance') else 'signal_timing')
        cases.append({'case_id': cid, 'target_law_id': LAW,
                      'target_type': 'boundary_probe',
                      'status': 'draft', 'rationale': 'Exact rider/signal/response alternative; original observations and legal judgments remain open.',
                      'paired_probe_id': 'sidewalk_overtake_alternatives',
                      'deliberate_differences': ['rider_kind', 'signal_timing', 'rider_response'],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'Compare original pass, signal, brake and rider-kind source measurements; no legal threshold inferred.',
                                'target_value_or_branch': name},
                      'variable_assignments': {
                          'rider_kind': {'kind': 'world_setup', 'value': case['rider_kind'], 'unit': 'category'},
                          'signal_timing': {'kind': 'world_setup', 'value': 'silent' if signal is None else ('before_pass' if signal < 300 else 'after_pass'), 'unit': 'category'},
                          'rider_response': {'kind': 'world_setup', 'value': config['case']['rider_response'], 'unit': 'category'}},
                      'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                      'recording_description': construction['recording_description']})
    first = cases[0]
    cases.insert(0, {'case_id': AID + '__baseline', 'target_law_id': None,
                     'target_type': 'baseline', 'status': 'draft',
                     'rationale': 'Shared source-bound sidewalk rider/pedestrian baseline without legal finding.',
                     'variable_assignments': first['variable_assignments'],
                     'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                     'recording_description': first['recording_description']})
    sweeps = [{'sweep_id': 'c142510-' + str(index), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'No reviewed original connected sidewalk, pedestrian waveform or qualitative adjudication range supplied.',
               'missing_inputs': ['reviewed connected sidewalk, original 900-frame attempt, independent judgment range']}
              for index, (phrase, note, _) in enumerate(judgments)]
    cases_ref = write('cases.json', {'cell_id': 'C142510', 'actor': ACTOR,
                                     'status': 'draft', 'sweep_specs': sweeps,
                                     'cases': cases})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID,
                                  'stages': {'relevance_batch': relevance_ref,
                                             'relevance': relevance_ref,
                                             'template': template_ref,
                                             'judgment_observables': judgment_refs,
                                             'bindings': binding_ref,
                                             'cases': cases_ref},
                                  'status': 'draft_original_source_pending'})


if __name__ == '__main__':
    main()
