"""Build source-faithful controlled-access exit semantic draft and open sweeps."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-263'
ACTOR = 'motor_vehicle_driver'
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
    relevance = {'cell_id': 'C228302', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('whose proximity constitutes an immediate hazard',
         'Original approaching vehicle occupancy, range, speed and interaction traces need human review.',
         'all_approaching_vehicles'),
        ('until the driver may proceed with reasonable safety',
         'Original ego wait and exit entry joined to every approaching vehicle need human review.',
         'precedence_duration')]
    parameters = [
        {'name': 'exit_policy', 'kind': 'world_setup',
         'range_or_domain': 'yield until clear, proceed before clear, or proceed between vehicles', 'unit': 'category'},
        {'name': 'approaching_count', 'kind': 'world_setup',
         'range_or_domain': 'one or two approaching vehicles', 'unit': 'count'},
        {'name': 'approach_headway_s', 'kind': 'world_setup',
         'range_or_domain': '3 or 9 seconds engineering probes, not legal cutoffs', 'unit': 's'}]
    template_ref = write('template.json', {
        'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': quote,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'The driver is about to exit a controlled-access highway into a general-road connection.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Yield right-of-way to all approaching highway vehicles whose proximity is an immediate hazard and continue yielding until reasonable safety.',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe all approaching vehicles and ego yielding through original exit interaction entry.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                      for phrase, note, _ in judgments]},
        'parameter_refs': parameters})
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        judgment_refs.append(write(f'judgment-{index}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'original source observation', 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'm and m/s' if channel == 'all_approaching_vehicles' else 's', 'description': note}],
                'limitations': ['Immediate hazard and reasonable safety have no supplied numeric legal threshold; original authority and motion are absent.']}}))
    binding_ref = write('bindings.json', {
        'cell_id': 'C228302', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in parameters]})
    cases = []
    for row in plan['cases']:
        cid = row['case_id']; name = cid.removeprefix(AID + '__')
        construction = json.loads((HERE / ('construction-compatibility-' + name + '.json')).read_text())
        design = row['construction']
        primary = 'approaching_count' if name == 'exit_yield_second' else ('approach_headway_s' if name == 'exit_distant_approach' else 'exit_policy')
        cases.append({'case_id': cid, 'target_law_id': LAW,
                      'target_type': 'boundary_probe', 'status': 'draft',
                      'rationale': 'Exact exit-only engineering and policy comparison; original road authority and legal judgments remain open.',
                      'paired_probe_id': 'controlled_access_exit_alternatives',
                      'deliberate_differences': ['exit_policy', 'approaching_count', 'approach_headway_s'],
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'Compare original exit entry, wait and all approaching vehicle histories; no legal threshold inferred.',
                                'target_value_or_branch': name},
                      'variable_assignments': {
                          'exit_policy': {'kind': 'world_setup', 'value': design['policy'], 'unit': 'category'},
                          'approaching_count': {'kind': 'world_setup', 'value': design['approaching_count'], 'unit': 'count'},
                          'approach_headway_s': {'kind': 'world_setup', 'value': design['approach_headway_s'], 'unit': 's'}},
                      'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                      'recording_description': construction['recording_description']})
    first = cases[0]
    cases.insert(0, {'case_id': AID + '__baseline', 'target_law_id': None,
                     'target_type': 'baseline', 'status': 'draft',
                     'rationale': 'Shared source-bound exit baseline without legal finding.',
                     'variable_assignments': first['variable_assignments'],
                     'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                     'recording_description': first['recording_description']})
    sweeps = [{'sweep_id': 'c228302-' + str(index), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'No reviewed original controlled-access authority, exit source, or qualitative judgment range supplied.',
               'missing_inputs': ['reviewed road authority, original exit attempt, independent judgment range']}
              for index, (phrase, note, _) in enumerate(judgments)]
    cases_ref = write('cases.json', {'cell_id': 'C228302', 'actor': ACTOR,
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
