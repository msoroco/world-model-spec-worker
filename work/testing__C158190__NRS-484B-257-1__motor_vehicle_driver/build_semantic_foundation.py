"""Draft exact-law relevance, template and cell binding stage proposals."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
LAW = ASSIGNMENT['law']
CELL = ASSIGNMENT['cell']
ACTOR = ASSIGNMENT['actor']
TEMPLATE_ID = LAW['id'] + '@' + ACTOR


def write(name, payload):
    (PROPOSALS / name).write_text(json.dumps(payload, indent=2) + '\n')


def main():
    relevance = {
        'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{
            'law_id': LAW['id'], 'quote': LAW['text'], 'applies_to': [ACTOR],
            'relevance_type': 'selected driver duty at a signed through-highway intersection',
            'confidence': 'high',
            'notes': 'The frozen cell says stop_sign while the selected branch requires yield_sign; preserve this cell/branch tension for local review. No actual sign or traffic observation is claimed.'
        }], 'borderline_excluded': [],
    }
    write('relevance-batch.json', relevance)
    write('relevance.json', relevance)
    judgments = [
        ('proper signs', 'Sign face, placement and governance require original Native and pixel evidence.'),
        ('point nearest the intersection where the driver has a view of approaching traffic on the through highway',
         'Sampled collision rays do not establish the nearest legally sufficient human view.'),
        ('immediate hazard', 'The statute supplies no numerical hazard cutoff.'),
        ('yield the right-of-way', 'Body and speed histories alone do not decide legal priority.'),
    ]
    params = [
        ('sign_type', 'world_setup', 'stop or yield sign with original Native sign and face readback'),
        ('stopping_reference', 'world_setup', 'stop line, near-side crosswalk or nearest-view location with original evidence'),
        ('through_vehicle_state', 'world_setup', 'approaching, already entered or absent through-highway actor staging'),
        ('commanded_approach_speed', 'controller', 'positive engineering m/s target; not a legal slowing cutoff'),
        ('commanded_view_speed', 'controller', 'positive engineering m/s target at the constructed view bracket'),
        ('ego_speed', 'subject_behavior', 'original Native measured m/s history'),
        ('through_highway_sight_clear', 'subject_behavior', 'original sampled sight-ray history; human visibility unresolved'),
        ('ego_in_intersection', 'subject_behavior', 'original ego-body overlap with sourced junction'),
    ]
    template = {
        'template_id': TEMPLATE_ID, 'law_id': LAW['id'], 'actor': ACTOR,
        'status': 'draft', 'quote': LAW['text'],
        'structure': {
            'law_id': LAW['id'],
            'activation': {'condition': 'proper sign governs a vehicle approaching the through-highway intersection, absent police-officer or traffic-signal control',
                           'numeric_conditions': []},
            'obligation': {'description': 'stop or yield at the stated reference hierarchy, then yield to through-highway vehicles already entered or approaching closely enough to constitute an immediate hazard while crossing or within the intersection',
                           'type': 'must', 'numeric_conditions': []},
            'exceptions': [{
                'trigger': 'traffic controlled by police officer or traffic-control signal',
                'effect': 'subsection-1 signed-intersection duty does not govern under that control',
                'replacement_obligation': 'unresolved under the controlling officer or signal rule',
                'source_clause': 'Except when traffic is being controlled by a police officer or a traffic-control signal:'
            }],
            'timing': {'description': 'stop/yield reference precedes entry; through-highway priority is assessed during the ego crossing or within-intersection interval',
                       'numeric_conditions': []},
            'judgment_calls_needed': [
                {'phrase': phrase, 'note': note} for phrase, note in judgments],
        },
        'parameter_refs': [
            {'name': name, 'kind': kind, 'range_or_domain': domain}
            for name, kind, domain in params],
    }
    write('template.json', template)
    binding = {
        'cell_id': CELL['cell_id'], 'actor': ACTOR, 'status': 'draft',
        'established_contexts': [
            'Frozen C158190 one-way-to-two-way intersection, travel maneuver and stop_sign cell control; the selected yield-sign branch is a documented scope tension, not an observed Native fact.'
        ],
        'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
        'context_refs': [],
        'fixed_parameters': [{'name': 'selected_cell', 'value': CELL['cell_id'],
                              'rationale': 'Frozen assignment identity'}],
        'variable_parameters': [
            {'name': name, 'kind': kind, 'range_or_domain': domain,
             'used_by_laws': [LAW['id']]}
            for name, kind, domain in params],
    }
    write('bindings.json', binding)
    print(json.dumps({'law_id': LAW['id'], 'template_id': TEMPLATE_ID,
                      'judgment_phrases': [j[0] for j in judgments],
                      'variable_parameters': len(params)}))


if __name__ == '__main__':
    main()
