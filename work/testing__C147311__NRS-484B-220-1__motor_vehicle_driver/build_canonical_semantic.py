"""Build exact four-case draft semantic chain from frozen one-way law text."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from one_way_direction import CASES


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROPOSALS = HERE / 'proposals'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / (name + '.json')
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}


def main() -> None:
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law_id, cell_id, actor = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
    quote = plan['law_text']
    if quote != assignment['law']['text'] or law_id != plan['law_id'] or cell_id != plan['cell_id']:
        raise ValueError('frozen law or cell differs')
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'confidence': 'high'}],
                 'borderline_excluded': []}
    r_batch = write('relevance-batch', relevance)
    r_cell = write('relevance', relevance)
    template_id = law_id + '@' + actor
    parameter_refs = [
        {'name': 'selected_lane', 'kind': 'world_setup',
         'unit': 'categorical', 'range_or_domain': 'lane one or lane two'},
        {'name': 'actual_direction', 'kind': 'world_setup',
         'unit': 'categorical', 'range_or_domain': 'designated or opposed'}]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {'activation': {'source_clause':
                    'Upon a highway designated and signposted for one-way traffic'},
                    'obligation': {'source_clause':
                        'a vehicle shall be driven only in the direction designated'},
                    'exceptions': [],
                    'timing': {'source_clause': 'Upon a highway designated and signposted for one-way traffic'},
                    'judgment_calls_needed': []},
                'parameter_refs': parameter_refs}
    t_ref = write('template', template)
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [], 'variable_parameters': [
                    {**entry, 'used_by_laws': [law_id]} for entry in parameter_refs]}
    b_ref = write('bindings', bindings)
    construction = json.loads((HERE / 'construction.json').read_text())
    description = construction['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Shared one-way source observation definition; no separate recording.',
              'recording_description': description, 'unresolved_judgment_calls': [],
              'variable_assignments': {'selected_lane': {'kind': 'world_setup', 'unit': 'categorical', 'value': 1},
                                       'actual_direction': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'designated'}}}]
    for case in CASES:
        case_id = HERE.name + '__' + case.name
        source = json.loads((HERE / ('construction.json' if case == CASES[0] else
                                       f'cases/{case.name}/construction.json')).read_text())
        cases.append({'case_id': case_id, 'target_law_id': law_id,
                      'target_type': 'compliant_attempt' if case.direction == 'designated' else 'violating_attempt',
                      'paired_probe_id': 'actual_direction_lane' + str(case.lane),
                      'deliberate_differences': ['actual_direction'],
                      'probe': {'primary_variable': 'actual_direction',
                                'comparison_or_standard': 'Original velocity projected on source-reviewed designated vector',
                                'target_value_or_branch': case.direction},
                      'rationale': 'Source-gated requested physical direction probe; no legal outcome is claimed.',
                      'recording_description': source['recording_description'],
                      'unresolved_judgment_calls': [],
                      'variable_assignments': {'selected_lane': {'kind': 'world_setup', 'unit': 'categorical', 'value': case.lane},
                                               'actual_direction': {'kind': 'world_setup', 'unit': 'categorical', 'value': case.direction}}})
    case_stage = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                  'source_assignment': HERE.name, 'source_law_text': quote,
                  'cases': cases, 'comparisons': plan['comparisons'],
                  'sweep_specs': [], 'sweeps_expanded': True}
    c_ref = write('cases', case_stage)
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': {'relevance_batch': r_batch, 'relevance': r_cell,
                        'template': t_ref, 'judgment_observables': [],
                        'bindings': b_ref, 'cases': c_ref}}
    write('semantic-index', index)
    print('Built one-law categorical semantic chain for four exact cases')


if __name__ == '__main__':
    main()
