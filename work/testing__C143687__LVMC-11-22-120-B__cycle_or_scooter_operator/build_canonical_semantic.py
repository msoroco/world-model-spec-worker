"""Build the exact bicycle sign/roadway categorical semantic chain."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PROPOSALS = HERE / 'proposals'
MOTIONS = ('posted_enter', 'posted_stop', 'posted_remain_trail')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(name: str, value: dict) -> dict:
    path = PROPOSALS / (name + '.json')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'path': str(path.relative_to(HERE)), 'sha256': sha(path)}


def main() -> None:
    assignment = json.loads((REPO / 'inputs' / HERE.name / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    law_id, cell_id, actor = (assignment[key] for key in ('law_id', 'cell_id', 'actor'))
    quote = assignment['law']['text']
    if quote != plan['law_text'] or law_id != plan['law_id'] or cell_id != plan['cell_id']:
        raise ValueError('frozen bicycle law or cell differs')
    relevance = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                 'relevant_laws': [{'law_id': law_id, 'quote': quote,
                                    'applies_to': [actor], 'confidence': 'high'}],
                 'borderline_excluded': []}
    r_batch = write('relevance-batch', relevance)
    r_cell = write('relevance', relevance)
    template_id = law_id + '@' + actor
    params = [
        {'name': 'posted_bicycle_roadway_restriction', 'kind': 'world_setup',
         'unit': 'categorical', 'range_or_domain': 'posted and source reviewed'},
        {'name': 'actual_bicycle_route', 'kind': 'world_setup',
         'unit': 'categorical', 'range_or_domain': 'enter governed roadway, stop before roadway, or remain trail'}]
    template = {'template_id': template_id, 'law_id': law_id, 'actor': actor,
                'status': 'draft', 'quote': quote,
                'structure': {'activation': {'source_clause':
                    'When signs are erected giving notice thereof'},
                    'obligation': {'source_clause':
                        'no person shall disobey the restriction stated on such signs'},
                    'exceptions': [],
                    'timing': {'source_clause': 'When signs are erected giving notice thereof'},
                    'judgment_calls_needed': []},
                'parameter_refs': params}
    t_ref = write('template', template)
    bindings = {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
                'context_refs': [], 'fixed_parameters': [], 'variable_parameters': [
                    {**entry, 'used_by_laws': [law_id]} for entry in params]}
    b_ref = write('bindings', bindings)
    description = json.loads((HERE / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': HERE.name + '__baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Shared source reviewed sign and route context; no separate recording.',
              'recording_description': description, 'unresolved_judgment_calls': [],
              'variable_assignments': {'posted_bicycle_roadway_restriction': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'posted'},
                                       'actual_bicycle_route': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'none'}}}]
    for suffix in MOTIONS:
        case_id = HERE.name + '__' + suffix
        source = json.loads((HERE / ('construction.json' if suffix == MOTIONS[0] else
                                       f'cases/{suffix}/construction.json')).read_text())
        route = {'posted_enter': 'governed roadway entry',
                 'posted_stop': 'stop before governed roadway',
                 'posted_remain_trail': 'trail-only travel'}[suffix]
        cases.append({'case_id': case_id, 'target_law_id': law_id,
                      'target_type': 'violating_attempt' if suffix == 'posted_enter' else 'compliant_attempt',
                      'paired_probe_id': 'posted_roadway_entry' if suffix != 'posted_remain_trail' else 'trail_vs_roadway_use',
                      'deliberate_differences': ['actual_bicycle_route'],
                      'probe': {'primary_variable': 'actual_bicycle_route',
                                'comparison_or_standard': 'Original roadway/trail segment history with reviewed sign source',
                                'target_value_or_branch': route},
                      'rationale': 'Requested physical route category; legal outcome remains unresolved.',
                      'recording_description': source['recording_description'],
                      'unresolved_judgment_calls': [],
                      'variable_assignments': {'posted_bicycle_roadway_restriction': {'kind': 'world_setup', 'unit': 'categorical', 'value': 'posted'},
                                               'actual_bicycle_route': {'kind': 'world_setup', 'unit': 'categorical', 'value': route}}})
    c_ref = write('cases', {'cell_id': cell_id, 'actor': actor, 'status': 'draft',
                            'source_assignment': HERE.name, 'source_law_text': quote,
                            'cases': cases, 'comparisons': plan['comparisons'],
                            'sweep_specs': [], 'sweeps_expanded': True})
    write('semantic-index', {'format': 'worker-semantic-delivery',
                             'assignment_id': HERE.name,
                             'stages': {'relevance_batch': r_batch, 'relevance': r_cell,
                                        'template': t_ref, 'judgment_observables': [],
                                        'bindings': b_ref, 'cases': c_ref}})


if __name__ == '__main__':
    main()
