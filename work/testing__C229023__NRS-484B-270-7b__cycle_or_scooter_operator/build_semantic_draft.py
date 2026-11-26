"""Build source-faithful passing proposals while original legal sweeps stay open."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-270-7b'
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
    relevance = {'cell_id': 'C229023', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('can do so safely',
         'Original road and cycle/motor body history, relative motion and surface clearance require independent safety review.',
         'surface_clearance'),
        ('without endangering himself or herself or the occupants of the motor vehicle',
         'Original operator, motor occupant and passing motion evidence require independent endangerment review.',
         'relative_station')]
    parameters = [
        {'name': 'cycle_kind', 'kind': 'world_setup',
         'range_or_domain': 'bicycle, electric bicycle, electric scooter', 'unit': 'category'},
        {'name': 'lateral_offset_request_m', 'kind': 'world_setup',
         'range_or_domain': '1.5 or 2.5 requested engineering meters', 'unit': 'm'},
        {'name': 'pass_policy', 'kind': 'world_setup',
         'range_or_domain': 'complete or abort', 'unit': 'category'}]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'Human operator of bicycle, electric bicycle, or electric scooter overtakes and passes a motor vehicle.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Pass only if it can be done safely without endangering the operator or motor-vehicle occupants.',
                                   'type': 'must_not_unless', 'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Review original approach, alongside and pass or abort history.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgments]},
                'parameter_refs': parameters}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        judgment_refs.append(write(f'judgment-{index}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'source observation',
                                 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'm',
                                     'description': note}],
                'limitations': ['Original physical and legal judgment remains pending; no numerical legal threshold is supplied.']}}))
    binding_ref = write('bindings.json', {
        'cell_id': 'C229023', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in parameters]})
    cases = []
    for case in plan['cases']:
        name = case['case_id'].removeprefix(AID + '__')
        config_path = HERE / ('config.json' if name == 'bicycle_wider_pass' else
                              'cases/' + name + '/config.json')
        description = json.loads(config_path.read_text())['case']['recording_description']
        assignments = {
            'cycle_kind': {'kind': 'world_setup', 'value': case['cycle_kind'],
                           'unit': 'category'},
            'lateral_offset_request_m': {'kind': 'world_setup',
                                         'value': case['lateral_offset_request_m'],
                                         'unit': 'm'},
            'pass_policy': {'kind': 'world_setup', 'value': case['pass_policy'],
                            'unit': 'category'}}
        primary = ('lateral_offset_request_m' if name == 'bicycle_closer_pass'
                   else 'pass_policy' if name == 'bicycle_abort' else 'cycle_kind')
        cases.append({'case_id': case['case_id'], 'target_law_id': LAW,
                      'target_type': 'boundary_probe', 'status': 'draft',
                      'rationale': 'Exact covered operator and pass alternative; original safety and endangerment remain open.',
                      'paired_probe_id': 'cycle_motor_overtake_alternatives',
                      'deliberate_differences': [primary],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'Compare original body clearance, relative station, closing speed and occupant evidence; no legal cutoff inferred.',
                                'target_value_or_branch': name},
                      'variable_assignments': assignments,
                      'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                      'recording_description': description})
    first = cases[0]
    cases.insert(0, {'case_id': AID + '__baseline', 'target_law_id': None,
                     'target_type': 'baseline', 'status': 'draft',
                     'rationale': 'Shared source-bound bicycle and occupied motor-vehicle setup without legal finding.',
                     'variable_assignments': first['variable_assignments'],
                     'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                     'recording_description': first['recording_description']})
    sweeps = [{'sweep_id': 'c229023-' + str(index), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'No reviewed original scene, 900-frame attempt or independent qualitative legal range supplied.',
               'missing_inputs': ['reviewed original scene, complete original capture and independent judgment range']}
              for index, (phrase, note, _) in enumerate(judgments)]
    cases_ref = write('cases.json', {'cell_id': 'C229023', 'actor': ACTOR,
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
