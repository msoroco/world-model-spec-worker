"""Author canonical LVMC 11.12.070(B) stage proposals without legal verdicts."""
import hashlib
import json
from pathlib import Path

from through_highway import ASSIGNMENT, CASES, ENGINEERING, LAW

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C179789', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('having so yielded', 'Preceding subsection A source and original entering-driver approach require independent review; speed alone is insufficient.', 'entering_antecedent'),
        ('yield right-of-way', 'Original two-actor route, proximity, conflict order and through-driver response need source-backed review.', 'through_driver_response'),
    ]
    params = [
        {'name': 'entering_maneuver', 'kind': 'world_setup', 'range_or_domain': 'enter or cross', 'unit': 'category'},
        {'name': 'through_request', 'kind': 'controller', 'range_or_domain': 'yield_request or continue_request', 'unit': 'category'},
        {'name': 'antecedent_pause_s', 'kind': 'controller', 'range_or_domain': '0 to 4 seconds engineering request; no legal cutoff', 'unit': 's'},
        {'name': 'through_approach_speed_mps', 'kind': 'controller', 'range_or_domain': '4 to 12 m/s engineering request; no legal cutoff', 'unit': 'm/s'},
        {'name': 'entering_preentry_pause_s', 'kind': 'subject_behavior', 'range_or_domain': 'original measured pause', 'unit': 's'},
        {'name': 'entering_preentry_min_speed_mps', 'kind': 'subject_behavior', 'range_or_domain': 'original measured speed', 'unit': 'm/s'},
        {'name': 'through_preentry_min_speed_mps', 'kind': 'subject_behavior', 'range_or_domain': 'original measured speed', 'unit': 'm/s'},
        {'name': 'first_conflict_frame', 'kind': 'subject_behavior', 'range_or_domain': 'original Native frame', 'unit': 'frame'},
    ]
    template_ref = write('template.json', {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': ACTOR, 'status': 'draft', 'quote': quote,
        'structure': {'law_id': LAW,
            'activation': {'condition': 'Driver on through highway approaches an intersection where the entering or crossing driver has so yielded.', 'numeric_conditions': []},
            'obligation': {'description': 'Yield right-of-way to the vehicle about to enter or cross the through highway.', 'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe antecedent and both approaching vehicles before and during intersection conflict.', 'numeric_conditions': []},
            'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _ in judgments]},
        'parameter_refs': params})
    jrefs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        jrefs.append(write(f'judgment-{index}.json', {'template_id': TEMPLATE,
            'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [{'name': channel, 'unit': 'original source observation', 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [{'name': 'entering_preentry_pause_s' if index == 0 else 'through_preentry_min_speed_mps', 'unit': 's' if index == 0 else 'm/s', 'description': 'Original source-bound engineering sweep measurement.'}], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'm and m/s', 'description': note}],
                'limitations': ['No exact judgment range or legal numeric cutoff is supplied; original antecedent and precedence require review.']}}))
    binding_ref = write('bindings.json', {'cell_id': 'C179789', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]})
    cases = []
    for row in plan['cases']:
        cid = row['case_id']; name = cid.removeprefix(ASSIGNMENT + '__')
        if name in ENGINEERING:
            continue
        construction = json.loads((HERE / ('construction-' + name + '.json')).read_text())
        maneuver, response = CASES[name]
        assignments = {
            'entering_maneuver': {'kind': 'world_setup', 'value': maneuver, 'unit': 'category'},
            'through_request': {'kind': 'controller', 'value': response, 'unit': 'category'},
            'antecedent_pause_s': {'kind': 'controller', 'value': None, 'unit': 's'},
            'through_approach_speed_mps': {'kind': 'controller', 'value': 8.0, 'unit': 'm/s'},
            'entering_preentry_pause_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
            'entering_preentry_min_speed_mps': {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s'},
            'through_preentry_min_speed_mps': {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s'},
            'first_conflict_frame': {'kind': 'subject_behavior', 'value': None, 'unit': 'frame'},
        }
        cases.append({'case_id': cid, 'target_law_id': LAW, 'target_type': 'boundary_probe',
            'status': 'draft', 'rationale': 'Exact enter/cross and through-driver response comparison with antecedent and legal judgment open.',
            'paired_probe_id': 'through_highway_enter_cross',
            'deliberate_differences': ['entering_maneuver', 'through_request'],
            'probe': {'primary_variable': 'through_request',
                'comparison_or_standard': 'Compare original two-actor source-backed response and conflict order without legal cutoff.',
                'target_value_or_branch': name},
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
            'recording_description': construction['recording_description']})
    first = cases[0]
    cases.insert(0, {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'status': 'draft',
        'rationale': 'Shared through-highway source context without legal finding.',
        'variable_assignments': first['variable_assignments'],
        'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
        'recording_description': first['recording_description']})
    sweeps = []
    for family, anchor, phrase_index, variable, observable, unit, low, high, spacing in (
        ('antecedent_pause', 'cross_yield', 0, 'antecedent_pause_s', 'entering_preentry_pause_s', 's', 0.0, 4.0, 2.0),
        ('precedence_speed', 'cross_continue', 1, 'through_approach_speed_mps', 'through_preentry_min_speed_mps', 'm/s', 4.0, 12.0, 4.0),
    ):
        phrase, note, _ = judgments[phrase_index]
        anchor_case = next(item for item in cases if item['case_id'] == ASSIGNMENT + '__' + anchor)
        assignments = dict(anchor_case['variable_assignments'])
        assignments[variable] = {'kind': 'controller', 'value': 'source-gated engineering request', 'unit': unit}
        sweeps.append({'sweep_id': ASSIGNMENT + '__' + family, 'target_law_id': LAW,
            'judgment_refs': [{'phrase': phrase, 'note': note}], 'status': 'complete',
            'mode': 'one_dimensional', 'landmarks': [],
            'rationale': 'Three original-source-gated engineering points; no legal threshold or verdict.',
            'recording_description': anchor_case['recording_description'],
            'variable_assignments': assignments,
            'axes': [{'variable': variable, 'observable': observable, 'unit': unit,
                'min': low, 'max': high, 'spacing': spacing,
                'range_rationale': 'Coverage requests at a reviewed original intersection, not a legal cutoff.',
                'spacing_rationale': 'Endpoint and midpoint engineering probes.',
                'feasibility_evidence': 'Reviewed route and 900 original Native frames required; source preflight rejects missing original site before actor spawn.',
                'measurement': {'method': 'Original two-actor Native frame and reviewed intersection source measurement',
                                'time_window': 'original approach before conflict entry', 'statistic': 'first'}}]})
    payload = {'cell_id': 'C179789', 'actor': ACTOR,
               'status': 'draft', 'sweep_specs': sweeps, 'cases': cases}
    import sys
    sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
    from batch_pipeline.sweeps import expand_sweeps
    expand_sweeps(payload, templates=[json.loads((HERE / 'proposals/template.json').read_text())],
                  bindings=json.loads((HERE / 'proposals/bindings.json').read_text()))
    cases_ref = write('cases.json', payload)
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ASSIGNMENT,
        'stages': {'relevance_batch': relevance_ref, 'relevance': relevance_ref,
                   'template': template_ref, 'judgment_observables': jrefs,
                   'bindings': binding_ref, 'cases': cases_ref},
        'status': 'draft_original_source_pending'})


if __name__ == '__main__':
    main()
