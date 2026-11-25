"""Build source-gated canonical red-left semantic stages for eight selected cases."""
from __future__ import annotations

import hashlib
import json
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


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(raw).hexdigest()}


def judgment(phrase: str, channel: str) -> dict:
    need = {'name': channel, 'unit': 'source record',
            'description': 'Source-bound original frame evidence for ' + phrase}
    return {'template_id': IDENT, 'phrase': phrase, 'note': '', 'status': 'draft',
            'observable_requirements': {
                'observables': [need],
                'context_inputs': [{'name': 'reviewed_red_left_site_packet', 'unit': 'source record',
                                    'description': 'Reviewed official signal, route and stop boundary'}],
                'sweep_dimensions': [{'name': 'conflict_response_request', 'unit': 'categorical',
                                      'description': 'Requested response, observed independently'}],
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
    base = PLAN['cases'][0]['draft_variables']
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
        suffix = row['case_id'].removeprefix(ROOT.name + '__')
        values = row['draft_variables']
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
    sweep_specs = [
        {'sweep_id': 'stop_reference_source_review', 'target_law_id': LAW['id'],
         'judgment_refs': [{'phrase': phrase_stop, 'note': ''}], 'status': 'incomplete',
         'rationale': 'The physical stop reference and feasible approach geometry require reviewed original sources.',
         'missing_inputs': ['Reviewed crosswalk/sign/marking hierarchy and original stop-reference geometry']},
        {'sweep_id': 'directed_yield_source_review', 'target_law_id': LAW['id'],
         'judgment_refs': [{'phrase': phrase_yield, 'note': ''}], 'status': 'incomplete',
         'rationale': 'Pedestrian and traffic route conflicts require reviewed signal-directed geometry.',
         'missing_inputs': ['Reviewed directed participant routes and original conflict-zone timing']},
    ]
    refs['cases'] = write('cases.json', {'cell_id': PLAN['cell_id'], 'actor': PLAN['actor'],
        'status': 'draft', 'cases': cases, 'sweep_specs': sweep_specs,
        'sweeps_expanded': True, 'semantic_status': 'partial_source_gated_judgment_sweeps'})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ROOT.name, 'stages': refs,
        'status': 'partial_source_gated_judgment_sweeps'})
    print('canonical source-gated semantic stages:', len(refs), 'cases:', len(cases))


if __name__ == '__main__':
    main()
