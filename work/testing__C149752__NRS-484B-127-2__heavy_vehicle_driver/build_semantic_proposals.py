"""Author source-faithful draft stages for exact truck-following law."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build_constructions import description
from truck_following import CASES
from native_packet import AID

HERE = Path(__file__).resolve().parent
OUT = HERE / 'proposals'
LAW = 'NRS-484B-127-2'
ACTOR = 'heavy_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
TEXT = ('The driver of any truck or combination of vehicles 80 inches or more in overall width, which is following a truck, or combination of vehicles 80 inches or more in overall width, shall, whenever conditions permit, leave a space of 500 feet so that an overtaking vehicle may enter and occupy such space without danger, but this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles. This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.')
JUDGMENTS = (
    ('whenever conditions permit', 'Review actual traffic and road circumstances independently.', 'map_lane_availability'),
    ('so that an overtaking vehicle may enter and occupy such space without danger',
     'Review original entrant and traffic history; physical gap alone does not establish absence of danger.', 'vehicle_inventory'),
    ('overtaking and passing any vehicle or combination of vehicles',
     'Measure whole-body opposing-lane advancement and return independently of controller phase.', 'original_body_vertices'),
)
PARAMS = (
    ('requested_gap_m', 'world_setup', 'below, at and above 500 feet', 'm'),
    ('subject_width_m', 'world_setup', 'below and above 80 inches', 'm'),
    ('lead_width_m', 'world_setup', 'below and above 80 inches', 'm'),
    ('same_direction_lanes', 'world_setup', 'one or two available lanes', '1'),
    ('pass_requested', 'controller', 'false or true', 'boolean'),
    ('entrant_requested', 'controller', 'false or true', 'boolean'),
)


def write(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(case):
    values = (case.gap_target_m, case.ego_width_target_m, case.lead_width_target_m,
              case.available_same_direction_lanes, case.passing, case.entering_vehicle)
    return {name: {'kind': kind, 'value': value, 'unit': unit}
            for (name, kind, _, unit), value in zip(PARAMS, values)}


def build():
    relevance = {'cell_id': 'C149752', 'actor': ACTOR, 'status': 'draft',
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
            'activation': {'condition': 'A truck or combination at least 80 inches wide follows another such truck on a highway with fewer than two available same-direction lanes.',
                           'numeric_conditions': [{'value': 80, 'unit': 'inches', 'relation': 'at least'}]},
            'obligation': {'description': 'When conditions permit, leave 500 feet for safe entry by an overtaking vehicle.',
                           'type': 'must', 'numeric_conditions': [{'value': 500, 'unit': 'feet', 'relation': 'space'}]},
            'exceptions': [{'source_clause': 'but this shall not prevent a truck or combination of vehicles from overtaking and passing any vehicle or combination of vehicles',
                            'description': 'Truck overtaking and passing remains permitted.'},
                           {'source_clause': 'This subsection does not apply to any vehicle or combination of vehicles while moving on a highway on which there are two or more lanes available for traffic moving in the same direction.',
                            'description': 'Subsection does not apply with two or more available same-direction lanes.'}],
            'timing': {'description': 'Observe following, possible entry and pass over original 45-second history.',
                       'numeric_conditions': []},
            'judgment_calls_needed': judgments},
        'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                            'unit': unit} for name, kind, domain, unit in PARAMS]}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(JUDGMENTS):
        evidence = {'name': channel, 'unit': next(c['unit'] for c in description()['channels']
                                                if c['name'] == channel), 'description': note}
        judgment_refs.append(write('judgment-' + str(index) + '.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note, 'status': 'draft',
            'observable_requirements': {'observables': [evidence], 'context_inputs': [],
                'sweep_dimensions': [], 'landmarks': [], 'recording_needs': [evidence],
                'limitations': ['Original traffic and source review remains required; no new legal cutoff is supplied.']}}))
    binding_ref = write('bindings.json', {'cell_id': 'C149752', 'actor': ACTOR,
        'status': 'draft', 'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                 'unit': unit, 'used_by_laws': [LAW]}
                                for name, kind, domain, unit in PARAMS]})
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
        'target_type': 'baseline', 'status': 'draft',
        'rationale': 'Shared truck-following context without a legal finding.',
        'variable_assignments': assignments(CASES[0]),
        'unresolved_judgment_calls': [phrase for phrase, _, _ in JUDGMENTS],
        'recording_description': description()}
    cases = [baseline]
    for case in CASES:
        cases.append({'case_id': AID + '__' + case.suffix,
            'target_law_id': LAW, 'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': 'Exact statutory distance, width, lane, passage, entry or circumstance construction; no legal verdict.',
            'paired_probe_id': 'truck_following_qualifications',
            'deliberate_differences': ['requested_gap_m', 'subject_width_m', 'lead_width_m',
                                      'same_direction_lanes', 'pass_requested', 'entrant_requested'],
            'probe': {'primary_variable': 'requested_gap_m',
                      'comparison_or_standard': 'Compare sealed original full-body and lane history with the exact statutory context.',
                      'target_value_or_branch': case.suffix},
            'variable_assignments': assignments(case),
            'unresolved_judgment_calls': [phrase for phrase, _, _ in JUDGMENTS],
            'recording_description': description()})
    cases_ref = write('cases.json', {'cell_id': 'C149752', 'actor': ACTOR,
        'status': 'draft', 'sweep_specs': [{
            'sweep_id': 'conditions_and_danger_review', 'target_law_id': LAW,
            'judgment_refs': judgments, 'status': 'incomplete', 'mode': 'joint',
            'axes': [], 'landmarks': [],
            'rationale': 'Exact statutory quantities and alternatives are prepared; conditions and danger require source review.',
            'missing_inputs': ['original traffic histories and reviewed road source',
                               'independent legal judgment of conditions and danger'],
            'variable_assignments': assignments(CASES[0]),
            'recording_description': description()}],
        'sweeps_expanded': True, 'cases': cases})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': AID, 'stages': {
            'relevance_batch': relevant_ref, 'relevance': relevant_ref,
            'template': template_ref, 'judgment_observables': judgment_refs,
            'bindings': binding_ref, 'cases': cases_ref},
        'status': 'draft_original_source_pending'})


if __name__ == '__main__':
    build()
