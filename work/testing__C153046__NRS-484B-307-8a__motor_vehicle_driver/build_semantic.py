"""Build source-gated canonical red-left semantic stages for eight selected cases."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
PLAN = json.loads((ROOT / 'case-plan.json').read_text())
LAW = ASSIGNMENT['law']
IDENT = LAW['id'] + '@' + ASSIGNMENT['actor']
RECORDING = json.loads((ROOT / 'cases' / PLAN['cases'][0]['case_id'].removeprefix(ROOT.name + '__') /
                        'construction.json').read_text())['recording_description']
for name, method, unit in (
    ('stop_reference_front_signed_distance',
     'Original minimum front-body offset to the reviewed applicable stop reference', 'm'),
    ('directed_conflict_release_delay',
     'Original time from sourced directed pedestrian conflict clearing to first turn request', 's')):
    if not any(channel['name'] == name for channel in RECORDING['channels']):
        RECORDING['channels'].append({'name': name, 'method': method, 'unit': unit,
            'reference_frame': 'source-sealed original Native frame map', 'sampling_rate_hz': 20,
            'time_window': 'full 45-second episode',
            'uncertainty': 'physical realization and legal classification remain unresolved'})


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(raw).hexdigest()}


def judgment(phrase: str, channel: str) -> dict:
    sweep_name = ('stop_reference_front_signed_distance' if channel == 'pre_entry_stop'
                  else 'directed_conflict_release_delay')
    sweep_unit = 'm' if channel == 'pre_entry_stop' else 's'
    need = {'name': channel, 'unit': 'source record',
            'description': 'Source-bound original frame evidence for ' + phrase}
    return {'template_id': IDENT, 'phrase': phrase, 'note': '', 'status': 'draft',
            'observable_requirements': {
                'observables': [need],
                'context_inputs': [{'name': 'reviewed_red_left_site_packet', 'unit': 'source record',
                                    'description': 'Reviewed official signal, route and stop boundary'}],
                'sweep_dimensions': [{'name': sweep_name, 'unit': sweep_unit,
                                      'description': 'Original physical quantity measured independently of controller request'}],
                'landmarks': [], 'recording_needs': [need],
                'limitations': ['Reviewed exact Native site and original frames are required; '
                                'no legal boundary is supplied.']}}


def main() -> None:
    quote = LAW['text']
    relevance = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW['id'], 'quote': quote,
                                    'applies_to': [PLAN['actor']],
                                    'relevance_type': 'assigned steady-red one-way left turn',
                                    'confidence': 'medium',
                                    'notes': 'Exact Native signal and route sources pending.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch.json', relevance),
            'relevance': write('relevance.json', relevance)}
    parameters = [{'name': name, 'kind': kind, 'range_or_domain': domain}
                  for name, kind, domain in (
                      ('stop_request', 'controller', 'complete stop or rolling request'),
                      ('approach_position', 'world_setup', 'extreme left or inner lane'),
                      ('receiving_direction', 'world_setup', 'one-way left or two-way route'),
                      ('conflict_response_request', 'controller',
                       'clear, pedestrian yield/advance, traffic yield/advance'),
                      ('stop_hold_margin_m', 'controller', '0.5 to 2.0 m engineering stop request'),
                      ('yield_release_delay_s', 'controller', '0 to 1 s engineering hold request'),
                      ('stop_reference_front_signed_distance', 'world_setup', 'pending original body measurement'),
                      ('directed_conflict_release_delay', 'world_setup', 'pending original timing measurement'),
                      ('signal_request', 'world_setup', 'official steady red alone'))]
    phrase_stop = 'must stop before entering the crosswalk on the nearest side of the intersection'
    phrase_yield = 'must yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection'
    template = {'template_id': IDENT, 'law_id': LAW['id'], 'actor': PLAN['actor'],
                'quote': quote, 'structure': {
                    'law_id': LAW['id'],
                    'activation': {'condition': 'Vehicle faces an official steady red signal alone.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Stop before the applicable near-side reference and remain until green, subject to the stated left-turn exception.',
                                   'type': 'must', 'numeric_conditions': []},
                    'exceptions': [{'trigger': 'After stopping, extreme-left one-way approach to a one-way road to the left',
                                    'effect': 'Permits left turn after the stop subject to yielding',
                                    'replacement_obligation': 'Yield to pedestrians and signal-directed traffic',
                                    'source_clause': 'situated on the extreme left of a one-way highway may proceed into the intersection for a left turn only when the intersecting highway is one-way to the left'}],
                    'timing': {'description': 'At the stop reference before entry and during any red-left turn.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase_stop, 'note': ''},
                                              {'phrase': phrase_yield, 'note': ''}]},
                'parameter_refs': parameters}
    refs['template'] = write('template.json', template)
    refs['judgment_observables'] = [
        write('judgment-stop.json', judgment(phrase_stop, 'pre_entry_stop')),
        write('judgment-yield.json', judgment(phrase_yield, 'directed_conflict'))]
    binding = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
               'established_contexts': ['Official steady red alone and one-way-left road require reviewed Native site source'],
               'law_refs': [{'template_id': IDENT, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{**row, 'used_by_laws': [LAW['id']]} for row in parameters]}
    refs['bindings'] = write('bindings.json', binding)
    cases = []
    base = dict(PLAN['cases'][0]['draft_variables'], stop_hold_margin_m=1.0,
                yield_release_delay_s=0.0,
                stop_reference_front_signed_distance='pending_original_measurement',
                directed_conflict_release_delay='pending_original_measurement')
    def assignments(values):
        return {p['name']: {'kind': p['kind'], 'value': values[p['name']],
                            'note': 'Requested setup/control; original behavior measured separately'}
                for p in parameters}
    cases.append({'case_id': ROOT.name + '__baseline', 'target_law_id': None,
                  'target_type': 'baseline', 'rationale': 'Shared reviewed signal and lane context; no outcome label.',
                  'variable_assignments': assignments(base),
                  'unresolved_judgment_calls': [], 'recording_description': RECORDING})
    pairs = {'stopped_leftmost_pedestrian_yield': ('pedestrian_response', 'conflict_response_request'),
             'stopped_leftmost_pedestrian_advance': ('pedestrian_response', 'conflict_response_request'),
             'stopped_leftmost_traffic_yield': ('traffic_response', 'conflict_response_request'),
             'stopped_leftmost_traffic_advance': ('traffic_response', 'conflict_response_request')}
    for row in PLAN['cases']:
        if row.get('sweep_id'):
            continue
        suffix = row['case_id'].removeprefix(ROOT.name + '__')
        values = dict(base, **row['draft_variables'])
        pair, primary = pairs.get(suffix, (suffix + '_standard',
                                          next((name for name in base if values[name] != base[name]),
                                               'stop_request')))
        differences = [name for name in base if values[name] != base[name]] or [primary]
        cases.append({'case_id': row['case_id'], 'target_law_id': LAW['id'],
                      'target_type': 'boundary_probe',
                      'rationale': 'Exact requested original-frame probe; physical and legal outcomes unresolved.',
                      'paired_probe_id': pair, 'deliberate_differences': differences,
                      'probe': {'primary_variable': primary,
                                'comparison_or_standard': 'same reviewed signal/stop source and separately measured original response',
                                'target_value_or_branch': values[primary]},
                      'variable_assignments': assignments(values),
                      'unresolved_judgment_calls': [phrase_stop, phrase_yield],
                      'recording_description': RECORDING})
    sweep_specs = []
    for name, phrase, variable, observable, unit, start, stop, spacing, method, values in (
        ('stop_reference_source_review', phrase_stop, 'stop_hold_margin_m',
         'stop_reference_front_signed_distance', 'm', 0.5, 2.0, 0.75,
         'Original minimum front-body offset to the reviewed applicable stop reference',
         dict(base, stop_request='complete_stop', conflict_response_request='no_conflict')),
        ('directed_yield_source_review', phrase_yield, 'yield_release_delay_s',
         'directed_conflict_release_delay', 's', 0.0, 1.0, 0.5,
         'Original time from sourced directed pedestrian conflict clearing to first turn request',
         dict(base, stop_request='complete_stop', conflict_response_request='pedestrian_yield'))):
        sweep_specs.append({'sweep_id': ROOT.name + '__' + name, 'target_law_id': LAW['id'],
            'judgment_refs': [{'phrase': phrase, 'note': ''}], 'status': 'complete',
            'mode': 'one_dimensional', 'rationale':
            'Fixed engineering controller requests; actual body motion, applicable source and legal judgment require original review.',
            'axes': [{'variable': variable, 'observable': observable, 'unit': unit,
                      'min': start, 'max': stop, 'spacing': spacing,
                      'measurement': {'method': method, 'time_window': 'original 20 Hz approach and turn episode',
                                      'statistic': 'min' if variable == 'stop_hold_margin_m' else 'last'},
                      'range_rationale': 'Bounded controller request supported by red_left_controller.py; no legal threshold is inferred.',
                      'spacing_rationale': 'Physical increments exceed one 20 Hz frame and separate requested maneuvers; no legal boundary is inferred.',
                      'feasibility_evidence': 'red_left_controller.py bounded request checks and source-gated synthetic diagnostic tests'}],
            'landmarks': [], 'variable_assignments': assignments(values),
            'recording_description': RECORDING,
            'production_source_requirements': ['reviewed C153046 official signal and applicable stop-reference geometry',
                'reviewed one-way lanes and directed participant routes',
                'retained original 20 Hz Native body, signal, participant and camera frames']})
    proposal = {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'], 'status': 'draft',
        'cases': cases, 'sweep_specs': sweep_specs, 'sweeps_expanded': False,
        'semantic_status': 'complete_source_gated_engineering_sweeps'}
    sys.path.insert(0, str(REPO / 'runtime'))
    from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(proposal, [template], binding)
    refs['cases'] = write('cases.json', proposal)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name, 'stages': refs,
        'status': 'complete_source_gated_engineering_sweeps'})
    print('canonical source-gated semantic stages:', len(refs), 'cases:', len(cases))


if __name__ == '__main__':
    main()
