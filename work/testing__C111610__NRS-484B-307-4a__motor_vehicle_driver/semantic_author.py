"""Author canonical stage drafts from the frozen C111610 law and case plan."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROPOSALS = ROOT / 'proposals'
ASSIGNMENT = ROOT.name
LAW = 'NRS-484B-307-4a'
ACTOR = 'motor_vehicle_driver'
TEMPLATE = LAW + '@' + ACTOR
PHRASE = 'yield the right-of-way to pedestrians lawfully within the adjacent crosswalk'
NOTE = 'The exact law supplies no numeric yielding or lawful-presence cutoff.'


def write(name, value):
    path = PROPOSALS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')
    return path


def ref(path):
    return {'path': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def parameter(name, kind, domain):
    return {'name': name, 'kind': kind, 'range_or_domain': domain}


def main():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    quote = plan['law_text']
    relevance = {'cell_id': 'C111610', 'actor': ACTOR, 'status': 'draft',
        'relevant_laws': [{'law_id': LAW, 'quote': quote,
            'applies_to': [ACTOR],
            'relevance_type': 'direct sole-green-turn-arrow intersection and adjacent-crosswalk duty',
            'confidence': 'high',
            'notes': 'Frozen branch selects a turning driver and adjacent-crosswalk pedestrian.'}],
        'borderline_excluded': []}
    relevance_batch = write('relevance_batch.json', relevance)
    relevance_single = write('relevance.json', relevance)
    params = [parameter('adjacent_crosswalk_occupancy', 'world_setup',
                        'clear or lawfully entered pedestrian occupying marked adjacent crosswalk'),
              parameter('other_traffic_occupancy', 'world_setup',
                        'absent or original-green-entered vehicle lawfully using the intersection'),
              parameter('arrow_direction', 'world_setup',
                        'official sole green left arrow facing ego'),
              parameter('ego_turn_controller', 'controller',
                        'source-gated connected left turn with observed yielding')]
    structure = {'law_id': LAW,
        'activation': {'condition': 'Driver faces an official green turn arrow alone at an intersection.',
                       'numeric_conditions': []},
        'obligation': {'description': 'Proceed only in the arrow direction while illuminated and yield to pedestrians lawfully within the adjacent crosswalk and other traffic lawfully using the intersection.',
                       'type': 'must', 'numeric_conditions': []},
        'exceptions': [],
        'timing': {'description': 'Original arrow illumination, pedestrian lawful entry and turning movement are joined by CARLA frame.',
                   'numeric_conditions': []},
        'judgment_calls_needed': [{'phrase': PHRASE, 'note': NOTE}]}
    template = write('template.json', {'template_id': TEMPLATE, 'law_id': LAW,
        'actor': ACTOR, 'quote': quote, 'structure': structure,
        'parameter_refs': params})
    description = json.loads((ROOT / 'config.json').read_text())['case']['recording_description']
    observables = [{'name': channel['name'], 'unit': channel['unit'],
                    'description': channel['method']} for channel in description['channels']]
    contexts = [{'name': item['name'], 'unit': item['unit'],
                 'description': item['method']} for item in description['context_inputs']]
    judgment = write('judgment-1.json', {'template_id': TEMPLATE,
        'phrase': PHRASE, 'note': NOTE, 'status': 'draft',
        'observable_requirements': {'observables': observables,
            'context_inputs': contexts,
            'sweep_dimensions': [{'name': 'adjacent_crosswalk_occupancy',
                'unit': 'categorical',
                'description': 'Clear versus lawfully occupied physical crosswalk; no legal threshold.'}],
            'landmarks': [], 'recording_needs': observables,
            'limitations': ['Lawful entry and right-of-way need source review.',
                            'Original sole-arrow asset and camera pixels require Native verification.']}})
    binding = write('bindings.json', {'cell_id': 'C111610', 'actor': ACTOR,
        'status': 'draft',
        'established_contexts': ['intersection', 'left turn', 'adjacent marked crosswalk'],
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in params]})
    stages = {'relevance_batch': ref(relevance_batch),
              'relevance': ref(relevance_single), 'template': ref(template),
              'judgment_observables': [ref(judgment)], 'bindings': ref(binding),
              'cases': ref(PROPOSALS / 'cases.json')}
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
        'assignment_id': ASSIGNMENT, 'stages': stages})


if __name__ == '__main__':
    main()
