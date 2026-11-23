"""Build source-bound draft semantic proposals; no legal verdict or physical receipt."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_case_plan import AID, KINDS, PAIRS
from recording_description import build as recording_description

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = json.loads((ROOT.parent.parent / 'inputs' / AID / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
LAW_ID = ASSIGNMENT['law_id']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = f'{LAW_ID}@{ACTOR}'
PHRASE = 'yield the right-of-way'
NOTE = 'No numeric yielding threshold or entitlement decision is supplied by this clause.'
NAMES = ('stop_request', 'approach_position', 'receiving_direction', 'conflict_response_request')
UNITS = {'stop_request': 'categorical request', 'approach_position': 'categorical lane request',
         'receiving_direction': 'categorical road request', 'conflict_response_request': 'categorical request'}
KINDS_BY_NAME = {'stop_request': 'controller', 'approach_position': 'world_setup',
                 'receiving_direction': 'world_setup', 'conflict_response_request': 'controller'}


def write(path: Path, value: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main() -> None:
    quote = LAW['text']
    relevance = {'status': 'draft', 'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': quote, 'applies_to': [ACTOR],
                                    'confidence': 'high'}], 'borderline_excluded': []}
    template = {'status': 'draft', 'law_id': LAW_ID, 'actor': ACTOR,
                'template_id': TEMPLATE_ID, 'quote': quote,
                'structure': {'activation': {'source_clause': 'Where the signal is a steady red signal alone'},
                              'obligation': {'source_clause': 'but must yield the right-of-way to pedestrians and other traffic proceeding as directed by the signal at the intersection.'},
                              'exceptions': [], 'timing': {'source_clause': 'After complying with the requirement to stop'},
                              'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]},
                'parameter_refs': [{'name': name, 'unit': UNITS[name]} for name in NAMES]}
    observable_items = [
        ('pedestrian right-of-way', 'structured actor history', 'Original pedestrian path and signal context'),
        ('other traffic right-of-way', 'structured actor history', 'Original other traffic path and signal context'),
        ('yield response', 'structured motion and control history', 'Original ego entry ordering and motion')]
    observable = {'status': 'draft', 'template_id': TEMPLATE_ID, 'phrase': PHRASE, 'note': NOTE,
                  'observable_requirements': {
                      'observables': [{'name': n, 'unit': u, 'description': d} for n, u, d in observable_items],
                      'context_inputs': [{'name': 'reviewed_signal_and_stop_hierarchy', 'unit': 'source record',
                                          'description': 'Source-reviewed official signal and conflict movement'}],
                      'sweep_dimensions': [{'name': 'conflict_response_request', 'unit': 'categorical request',
                                            'description': 'Requested response variation, with realized response measured separately'}],
                      'landmarks': [],
                      'recording_needs': [{'name': n, 'unit': u, 'description': d} for n, u, d in observable_items],
                      'limitations': ['No source-backed numerical right-of-way judgment is supplied.',
                                      'Actual participant motion and physical visibility require original capture.']}}
    binding = {'status': 'draft', 'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': n, 'kind': KINDS_BY_NAME[n],
                                        'range_or_domain': ', '.join(sorted({v[i] for v in KINDS.values()})),
                                        'used_by_laws': [LAW_ID]} for i, n in enumerate(NAMES)]}
    pair_for = {}
    for pair, (left, right, _) in PAIRS.items():
        pair_for.setdefault(left, pair)
        pair_for.setdefault(right, pair)
    cases = []
    baseline_values = KINDS['stopped_leftmost_clear']
    for suffix, values in [('baseline_reference', baseline_values), *KINDS.items()]:
        base = suffix == 'baseline_reference'
        changed = [n for n, left, right in zip(NAMES, baseline_values, values) if left != right]
        assignments = {n: {'kind': KINDS_BY_NAME[n], 'value': v, 'unit': UNITS[n]}
                       for n, v in zip(NAMES, values)}
        case = {'case_id': AID + '__' + suffix, 'target_law_id': LAW_ID,
                'target_type': 'baseline' if base else 'judgment_sweep',
                'rationale': 'Shared fixed reference' if base else 'Isolated physical attempt for exact assigned left-turn branch; outcome remains unmeasured.',
                'variable_assignments': assignments,
                'recording_description': recording_description(),
                'unresolved_judgment_calls': [{'phrase': PHRASE, 'note': NOTE}]}
        if not base:
            primary = changed[0] if changed else 'stop_request'
            case.update({'paired_probe_id': pair_for.get(suffix, 'clear_reference'),
                         'deliberate_differences': changed,
                         'probe': {'primary_variable': primary,
                                   'comparison_or_standard': 'Original source clause and measured physical attempt; no legal verdict',
                                   'target_value_or_branch': assignments[primary]['value']}})
        cases.append(case)
    case_stage = {'status': 'draft', 'cell_id': ASSIGNMENT['cell_id'], 'actor': ACTOR,
                  'cases': cases, 'sweep_specs': [{
                      'sweep_id': 'yield_range_pending_source', 'target_law_id': LAW_ID,
                      'judgment_refs': [{'phrase': PHRASE, 'note': NOTE}],
                      'rationale': 'Original source and physical geometry are required before freezing a judgment range.',
                      'status': 'incomplete',
                      'missing_inputs': ['Source-reviewed conflict geometry and participant behavior',
                                         'Original feasible Native variation and measured range']} ]}
    refs = {'relevance_batch': write(ROOT / 'proposals/relevance-batch.json', relevance),
            'relevance': write(ROOT / 'proposals/relevance.json', relevance),
            'template': write(ROOT / 'proposals/template.json', template),
            'judgment_observables': [write(ROOT / 'proposals/judgment-observables.json', observable)],
            'bindings': write(ROOT / 'proposals/bindings.json', binding),
            'cases': write(ROOT / 'proposals/cases.json', case_stage)}
    write(ROOT / 'proposals/semantic-index.json',
          {'format': 'worker-semantic-delivery', 'assignment_id': AID, 'stages': refs})
    print('six canonical draft stages, eight exact cases and one unresolved source-bound judgment sweep')


if __name__ == '__main__':
    main()
