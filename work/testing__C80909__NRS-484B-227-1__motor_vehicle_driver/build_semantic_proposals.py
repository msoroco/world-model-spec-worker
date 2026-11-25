"""Draft source-grounded canonical stages for the exact C80909 left-turn cell."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW = 'NRS-484B-227-1'
CELL = 'C80909'
ACTOR = 'motor_vehicle_driver'
SUFFIXES = ('left_through_opening', 'left_across_blocked_divider',
            'left_at_established_crossover', 'left_right_roadway_continuation')
PARAMETERS = (
    ('route_selection', 'controller', 'authored opening, blocked-space, crossover or continuation route'),
    ('crossing_location', 'world_setup', 'sourced opening, divider exterior or established crossover'),
    ('public_authority_source', 'world_setup', 'separate source for established crossover; pending review'),
    ('ego_body_crossing_observed', 'subject_behavior', 'original complete-body movement, never a guaranteed outcome'),
)


def write(name, value):
    folder = ROOT / 'proposals'
    folder.mkdir(exist_ok=True)
    path = folder / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(suffix):
    place = {'left_through_opening': 'physical_barrier_opening',
             'left_across_blocked_divider': 'outside_named_opening',
             'left_at_established_crossover': 'crossover',
             'left_right_roadway_continuation': 'right_hand_roadway'}[suffix]
    values = {'route_selection': suffix, 'crossing_location': place,
              'public_authority_source': 'required_separate_review' if place == 'crossover' else 'not_invoked',
              'ego_body_crossing_observed': None}
    units = {'route_selection': 'route kind', 'crossing_location': 'source category',
             'public_authority_source': 'source status',
             'ego_body_crossing_observed': 'structured record'}
    return {name: {'kind': kind, 'value': values[name], 'unit': units[name]}
            for name, kind, _ in PARAMETERS}


def build():
    assignment = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    text = assignment['law']['text']
    quote = ('Every vehicle driven upon a divided highway must be driven only upon the right-hand roadway '
             'and must not be driven over, across or within any dividing space, barrier or section or make '
             'any left turn, semicircular turn or U-turn, except through an opening in the barrier or '
             'dividing section or space or at a crossover or intersection established by a public authority.')
    exception = ('except through an opening in the barrier or dividing section or space '
                 'or at a crossover or intersection established by a public authority.')
    if quote not in text or exception not in text:
        raise ValueError('Exact subsection 1 source quote changed')
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'relevance_type': 'divided-highway left turn',
                                    'confidence': 'high',
                                    'notes': 'This cell binds a 90-degree left turn; C126120 retains U-turn coverage.'}],
                 'borderline_excluded': []}
    template_id = LAW + '@' + ACTOR
    template = {'template_id': template_id, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'vehicle is driven on a divided highway',
                                             'numeric_conditions': []},
                              'obligation': {'type': 'must_not',
                                             'description': 'drive outside the right-hand roadway, cross the divider, or make a left turn outside the stated opening/crossover exceptions',
                                             'numeric_conditions': []},
                              'exceptions': [{'trigger': 'physical opening or public-authority-established crossover or intersection',
                                              'effect': 'the stated turning/crossing prohibition has an exception at the sourced place',
                                              'replacement_obligation': 'retain right-hand-roadway and actual opening/crossover context for review',
                                              'source_clause': exception}],
                              'timing': {'description': 'while driving, crossing the divider or making the left turn',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': []},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in PARAMETERS]}
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Source-reviewed divided highway with a 90-degree left-turn alternative and other vehicle.'],
               'law_refs': [{'template_id': template_id, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain, 'used_by_laws': [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    description = json.loads((ROOT / 'construction.json').read_text())['recording_description']
    cases = [{'case_id': ASSIGNMENT + '__shared_baseline', 'target_law_id': None,
              'target_type': 'baseline', 'rationale': 'Shared geometry and observation reference, not a selected recording.',
              'variable_assignments': assignments('left_through_opening'),
              'unresolved_judgment_calls': [], 'recording_description': description}]
    kinds = {'left_through_opening': 'compliant_attempt',
             'left_across_blocked_divider': 'violating_attempt',
             'left_at_established_crossover': 'compliant_attempt',
             'left_right_roadway_continuation': 'compliant_attempt'}
    for suffix in SUFFIXES:
        construction = ROOT / ('construction.json' if suffix == SUFFIXES[0]
                               else 'cases/' + suffix + '/construction.json')
        item = json.loads(construction.read_text())
        cases.append({'case_id': item['case_id'], 'target_law_id': LAW,
                      'target_type': kinds[suffix],
                      'rationale': 'Planned physical branch target; actual motion, authority and legal conclusion remain unverified.',
                      'variable_assignments': assignments(suffix),
                      'unresolved_judgment_calls': [],
                      'recording_description': item['recording_description'],
                      'paired_probe_id': 'divided_road_left_turn_alternatives',
                      'deliberate_differences': ['route_selection', 'crossing_location',
                                                 'public_authority_source'],
                      'probe': {'primary_variable': 'route_selection',
                                'comparison_or_standard': 'same divided-highway and camera contract with a declared route/location change',
                                'target_value_or_branch': suffix}})
    proposal = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                'cases': cases, 'sweep_specs': [], 'sweeps_expanded': True}
    reference = write('relevance.json', relevance)
    stages = {'relevance_batch': reference, 'relevance': reference,
              'template': write('template.json', template),
              'judgment_observables': [], 'bindings': write('bindings.json', binding),
              'cases': write('cases.json', proposal)}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': ASSIGNMENT, 'stages': stages})


if __name__ == '__main__':
    build()
