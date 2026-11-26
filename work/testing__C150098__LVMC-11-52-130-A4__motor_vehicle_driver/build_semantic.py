"""Author canonical hydrant proposals while authority judgments remain open."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hydrant import ASSIGNMENT, CASES

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LAW = 'LVMC-11-52-130-A4'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C150098', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('parallel parking is permitted', 'Location-specific municipal parking permission must be reviewed.', 'parallel_parking_authority'),
        ('necessary to avoid conflict with other traffic in compliance with law', 'Original traffic conflict, necessity and lawful response require independent review.', 'exception_source'),
        ('directions of a police officer', 'Original officer authority and direction must be reviewed.', 'exception_source'),
        ('directions of a traffic control device', 'Original device authority and direction must be reviewed.', 'exception_source'),
    ]
    params = [
        {'name': 'hydrant_side', 'kind': 'world_setup', 'range_or_domain': 'upstream or downstream', 'unit': 'category'},
        {'name': 'requested_body_hydrant_gap_m', 'kind': 'controller', 'range_or_domain': '4.422, 4.572 or 4.722 m engineering targets', 'unit': 'm'},
        {'name': 'vehicle_activity', 'kind': 'controller', 'range_or_domain': 'stop, stand or park', 'unit': 'category'},
        {'name': 'exception_source_kind', 'kind': 'world_setup', 'range_or_domain': 'none, lawful conflict, police or device direction', 'unit': 'category'},
        {'name': 'measured_original_gap_m', 'kind': 'subject_behavior', 'range_or_domain': 'original target-side body/hydrant gap', 'unit': 'm'},
    ]
    template_ref = write('template.json', {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': ACTOR, 'status': 'draft', 'quote': quote,
        'structure': {'law_id': LAW,
            'activation': {'condition': 'Physical fire hydrant and location where parallel parking is permitted.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Do not stop, stand or park within fifteen feet of the hydrant absent a sourced necessity or direction exception.',
                           'type': 'must_not', 'numeric_conditions': [{'variable': 'statutory_hydrant_distance',
                               'value': 15, 'unit': 'ft', 'operator': 'within'}]},
            'exceptions': [{'source_clause': 'necessary to avoid conflict with other traffic in compliance with law'},
                           {'source_clause': 'the directions of a police officer or a traffic control device'}],
            'timing': {'description': 'Observe the vehicle activity and hydrant throughout the original approach and dwell.',
                       'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments]},
        'parameter_refs': params})
    jrefs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        jrefs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [{'name': channel,
                'unit': 'reviewed source', 'description': note}], 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'reviewed source',
                                     'description': note}],
                'limitations': ['Original municipal authority and exception necessity remain for local independent review; no numeric legal cutoff is invented.']}}))
    binding_ref = write('bindings.json', {'cell_id': 'C150098', 'actor': ACTOR,
        'status': 'draft', 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]})
    cases = []
    for case in CASES:
        case_id = ASSIGNMENT + '__' + case.suffix
        construction = json.loads((HERE / ('construction-' + case.suffix + '.json')).read_text())
        values = {'hydrant_side': case.side,
                  'requested_body_hydrant_gap_m': case.gap_m,
                  'vehicle_activity': case.activity,
                  'exception_source_kind': case.exception}
        assignments = {item['name']: {'kind': item['kind'],
            'value': values.get(item['name']), 'unit': item['unit']} for item in params}
        cases.append({'case_id': case_id, 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': 'Exact parallel-parking hydrant boundary, activity and sourced exception observation; no legal verdict.',
            'paired_probe_id': 'parallel_hydrant_boundary_activity_exception',
            'deliberate_differences': ['hydrant_side', 'requested_body_hydrant_gap_m',
                                      'vehicle_activity', 'exception_source_kind'],
            'probe': {'primary_variable': 'requested_body_hydrant_gap_m',
                      'comparison_or_standard': 'Compare original target-side body gap and sourced authority across exact cases.',
                      'target_value_or_branch': case.suffix,
                      'threshold_ref': 'obligation.numeric_conditions[0]',
                      'operator': 'within', 'unit': 'ft',
                      'test_value': case.gap_m / 0.3048},
            'epsilon_used': {'value': 0.15 / 0.3048, 'unit': 'ft',
                             'rationale': 'Engineering target offset of 0.15 m around the exact fifteen-foot statutory value; not a legal tolerance.'},
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
            'recording_description': construction['recording_description']})
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Shared one-way curb/hydrant context without legal finding.',
                'variable_assignments': cases[0]['variable_assignments'],
                'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                'recording_description': cases[0]['recording_description']}
    sweep = {'sweep_id': 'reviewed_hydrant_authority', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments],
        'status': 'incomplete', 'mode': 'joint', 'axes': [], 'landmarks': [],
        'rationale': 'Municipal permission, physical hydrant and exception sources require local review before judgment sweep binding.',
        'missing_inputs': ['reviewed parallel-parking permission and hydrant survey',
                           'original traffic, officer and device direction source'],
        'variable_assignments': cases[0]['variable_assignments'],
        'recording_description': cases[0]['recording_description']}
    cases_ref = write('cases.json', {'cell_id': 'C150098', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [sweep], 'sweeps_expanded': True,
        'cases': [baseline, *cases]})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ASSIGNMENT,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': jrefs,
                   'bindings': binding_ref, 'cases': cases_ref},
        'status': 'draft_original_source_pending'})


if __name__ == '__main__':
    build()
