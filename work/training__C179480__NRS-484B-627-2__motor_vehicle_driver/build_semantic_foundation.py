"""Build source-faithful draft semantic stages for NRS 484B.627(2)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
PROPOSALS = HERE / 'proposals'
LAW = ASSIGNMENT['law']
LAW_ID = LAW['id']
ACTOR = ASSIGNMENT['actor']
CELL_ID = ASSIGNMENT['cell_id']
TEMPLATE_ID = LAW_ID + '@' + ACTOR


def write(name, value):
    target = PROPOSALS / name
    target.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    return target


def observable(name, description):
    return {'name': name, 'unit': 'structured', 'description': description}


def judgment(phrase, note, needs, limitation):
    return {'template_id': TEMPLATE_ID, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': needs, 'context_inputs': [], 'sweep_dimensions': [],
                'landmarks': [], 'recording_needs': needs,
                'limitations': [limitation]}}


def build():
    quote = LAW['text']
    relevance = {'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW_ID, 'quote': quote,
                                    'applies_to': [ACTOR], 'relevance_type': 'specific_match',
                                    'confidence': 'medium',
                                    'notes': 'The paved-road stop cell can stage complete stops and following-traffic effects; statutory exceptions and control compatibility need original-source review.'}],
                 'borderline_excluded': []}
    write('relevance_batch.json', relevance)
    write('relevance.json', relevance)
    judgments = [
        ('normal and reasonable movement of traffic',
         'The law provides no numeric impediment threshold.',
         [observable('traffic_effect_evidence', 'Original following-traffic speed, deceleration and gap history joined to the roadway stop.')],
         'Measured traffic effects inform but do not decide normal and reasonable movement.'),
        ('necessary for safe operation',
         'Safety necessity depends on the actual hazard and feasible alternative action.',
         [observable('hazard_actor_state', 'Original hazard body, motion, lane and identity history.'),
          observable('ego_hazard_gap_history', 'Original frame-joined ego-to-hazard separation and stopping history.')],
         'Synthetic hazard geometry does not establish necessity; every selected case must preserve absence or presence as original evidence.'),
        ('in compliance with law',
         'Governing stop control and legal applicability require independent source review.',
         [observable('governing_control_readback', 'Original governing-control actor identity, ego association and per-frame state.')],
         'A red state alone does not establish that a stop was legally required or compliant; the control must fit the selected catalog cell.'),
    ]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': ACTOR,
                'status': 'draft', 'quote': quote, 'structure': {
                    'activation': {'source_clause': 'bring a vehicle to a complete stop upon a roadway so as to impede or block the normal and reasonable movement of traffic',
                                   'condition': 'A complete roadway stop with measured effect on normal and reasonable movement; original sources required.'},
                    'obligation': {'type': 'must_not', 'actor': 'person',
                                   'action': 'bring a vehicle to a complete stop upon a roadway so as to impede or block the normal and reasonable movement of traffic',
                                   'source_clause': 'A person shall not bring a vehicle to a complete stop upon a roadway so as to impede or block the normal and reasonable movement of traffic'},
                    'exceptions': [{'source_clause': 'the stop is necessary for safe operation',
                                    'effect': 'exception to prohibition; necessity requires independent review'},
                                   {'source_clause': 'in compliance with law',
                                    'effect': 'exception to prohibition; governing law and compliance require independent review'}],
                    'timing': {'source_clause': 'bring a vehicle to a complete stop upon a roadway',
                               'description': 'At the complete roadway stop and its effect on other traffic.'},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note, _, _ in judgments]},
                'parameter_refs': []}
    write('template.json', template)
    for phrase, note, needs, limitation in judgments:
        name = {'normal and reasonable movement of traffic': 'traffic_movement',
                'necessary for safe operation': 'safe_operation',
                'in compliance with law': 'legal_compliance'}[phrase]
        write('judgment_observables_' + name + '.json', judgment(phrase, note, needs, limitation))
    variables = [
        ('roadway_stop_placement', 'world_setup', 'Surveyed travel-lane or shoulder stop target; actual roadway footprint measured.'),
        ('other_vehicle_hazard', 'world_setup', 'Frozen other-vehicle control, with observed hazard presence or absence.'),
        ('governing_stop_control', 'world_setup', 'Source-verified governing legal stop context; compatibility with C179480 unresolved.'),
        ('ego_stop_controller', 'controller', 'Requested stop trajectory; actual completion measured from Native pose and speed.'),
        ('following_vehicle_controller', 'controller', 'Fixed following actor route and response policy across roadway-stop comparison.'),
    ]
    binding = {'cell_id': CELL_ID, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': [{'name': 'paved_road_other_vehicle_stop',
                                         'source': 'frozen C179480 catalog layout, maneuver and control'}],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain,
                                        'used_by_laws': [LAW_ID]}
                                       for name, kind, domain in variables]}
    write('bindings.json', binding)
    return len(judgments)


if __name__ == '__main__':
    print('draft judgments:', build())
