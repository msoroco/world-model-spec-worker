"""Author source-faithful draft semantic stages for C24751."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import description
from flashing_red_native import ASSIGNMENT, CASES

HERE = Path(__file__).resolve().parent
OUT = HERE / 'proposals'
LAW = 'NRS-484B-310-1'
ACTOR = 'heavy_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
TEXT = ('Whenever an illuminated flashing red or yellow signal is used in conjunction with an official traffic-control device, it shall require obedience by vehicular traffic as follows: When a red lens is illuminated with rapid intermittent flashes, drivers of vehicles shall stop before entering the nearest crosswalk in an intersection or at a limit line when marked, or, if none, then before entering the intersection, and the right to proceed shall be subject to the rules applicable after making a required stop.')
JUDGMENTS = (
    ('official traffic-control device', 'Review official device identity and which approach it governs.', 'signal_flash'),
    ('nearest crosswalk in an intersection or at a limit line when marked, or, if none, then before entering the intersection',
     'Review the actual surveyed stop reference; do not infer an extra priority or numeric tolerance.', 'stop_reference'),
    ('rules applicable after making a required stop',
     'Preserve incorporated post-stop rules for independent source review.', 'complete_cessation'),
)
PARAMS = (
    ('stop_reference_kind', 'world_setup', 'crosswalk, marked line or unmarked entry', 'category'),
    ('requested_stop_offset_m', 'controller', 'engineering approach stop target', 'm'),
    ('measured_front_at_stop_m', 'subject_behavior', 'original front position at complete cessation', 'm'),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    return {
        'stop_reference_kind': {'kind': 'world_setup', 'value': case.reference, 'unit': 'category'},
        'requested_stop_offset_m': {'kind': 'controller', 'value': case.stop_offset_m, 'unit': 'm'},
        'measured_front_at_stop_m': {'kind': 'subject_behavior', 'value': None, 'unit': 'm'},
    }


def build():
    relevance = {'cell_id': 'C24751', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': TEXT,
                           'applies_to': [ACTOR], 'confidence': 'high'}],
        'borderline_excluded': []}
    relevant_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [{'phrase': phrase, 'note': note} for phrase, note, _ in JUDGMENTS]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
        'status': 'draft', 'quote': TEXT,
        'structure': {
            'law_id': LAW,
            'activation': {'condition': 'Illuminated flashing red signal used with an official traffic-control device.',
                           'numeric_conditions': []},
            'obligation': {'description': 'Stop before the source-surveyed crosswalk, marked limit line, or unmarked intersection entry.',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [],
            'timing': {'description': 'Observe rapid intermittent red and complete cessation before entry; retain post-stop history.',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                            'unit': unit} for name, kind, domain, unit in PARAMS]}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(JUDGMENTS):
        evidence = {'name': channel, 'unit': next(c['unit'] for c in description()['channels']
                                                if c['name'] == channel),
                    'description': note}
        judgment_refs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [evidence], 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [], 'recording_needs': [evidence],
                'limitations': ['Original physical and source review remains required; no legal threshold is supplied.']}}))
    binding = {'cell_id': 'C24751', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': name, 'kind': kind,
                                  'range_or_domain': domain, 'unit': unit,
                                  'used_by_laws': [LAW]}
                                 for name, kind, domain, unit in PARAMS]}
    binding_ref = write('bindings.json', binding)
    baseline = {'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Shared flashing-red heavy-vehicle approach context without legal finding.',
                'variable_assignments': assignments(CASES[0]),
                'unresolved_judgment_calls': [phrase for phrase, _, _ in JUDGMENTS],
                'recording_description': description()}
    cases = [baseline]
    for case in CASES:
        cases.append({'case_id': ASSIGNMENT + '__' + case.suffix,
            'target_law_id': LAW, 'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': 'Exact physical stop-reference alternative and original front cessation; no legal verdict.',
            'paired_probe_id': 'flashing_red_stop_reference',
            'deliberate_differences': ['stop_reference_kind', 'requested_stop_offset_m'],
            'probe': {'primary_variable': 'requested_stop_offset_m',
                      'comparison_or_standard': 'Compare original front position at complete cessation against surveyed reference.',
                      'target_value_or_branch': case.suffix},
            'variable_assignments': assignments(case),
            'unresolved_judgment_calls': [phrase for phrase, _, _ in JUDGMENTS],
            'recording_description': description()})
    cases_ref = write('cases.json', {'cell_id': 'C24751', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{
            'sweep_id': 'post_stop_applicable_rules', 'target_law_id': LAW,
            'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note, _ in JUDGMENTS],
            'status': 'incomplete', 'mode': 'joint', 'axes': [], 'landmarks': [],
            'rationale': 'Exact physical references are prepared; original device authority and incorporated post-stop rules await source review.',
            'missing_inputs': ['reviewed official-device source and original packet',
                               'separate incorporated post-stop rules and original traffic history'],
            'variable_assignments': assignments(CASES[0]),
            'recording_description': description()}],
        'sweeps_expanded': True, 'cases': cases})
    index = {'format': 'worker-semantic-delivery', 'assignment_id': ASSIGNMENT,
        'stages': {'relevance_batch': relevant_ref, 'relevance': relevant_ref,
                   'template': template_ref, 'judgment_observables': judgment_refs,
                   'bindings': binding_ref, 'cases': cases_ref},
        'status': 'draft_original_source_pending'}
    write('semantic-index.json', index)


if __name__ == '__main__':
    build()
