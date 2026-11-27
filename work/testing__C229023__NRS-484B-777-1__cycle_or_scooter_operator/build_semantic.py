"""Source-faithful canonical stage proposals for 777(1) right-side passes."""

import hashlib
import json
from pathlib import Path

from rightside import CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
LAW = 'NRS-484B-777-1'
ACTOR = 'cycle_or_scooter_operator'
TEMPLATE = LAW + '@' + ACTOR


def write(name, value):
    path = HERE / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    assignment = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    quote = assignment['law']['text']
    relevance = {'cell_id': 'C229023', 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': quote,
                                    'applies_to': [ACTOR], 'confidence': 'high'}],
                 'borderline_excluded': []}
    relevance_ref = write('relevance.json', relevance)
    write('relevance-batch.json', relevance)
    judgments = [
        ('lawful rate of speed commensurate with the speed of any nearby traffic',
         'Source-sealed lawful-speed basis and original cycle/nearby-traffic histories; legal relation unresolved.',
         'cycle_speed'),
        ('would not be safe',
         'Original right-side impediment, lane/body width, passing motion and physical clearance; safety judgment unresolved.',
         'right_access_width'),
        ('as near to the right side of the roadway as practicable',
         'Original cycle body edge, roadway right boundary and impediments over the full pass; practicability unresolved.',
         'right_edge_distance'),
        ('exercising due care',
         'Original passing phases, target motion, body clearance and traffic context; due care unresolved.',
         'surface_clearance'),
        ('too narrow for a bicycle and a vehicle to travel safely side by side',
         'Original lane and participant body widths plus motion; legal safety remains unresolved.',
         'lane_width'),
    ]
    parameters = [
        {'name': 'cycle_kind', 'kind': 'world_setup',
         'range_or_domain': 'bicycle or electric scooter', 'unit': 'category'},
        {'name': 'requested_lateral_target_m', 'kind': 'world_setup',
         'range_or_domain': '0.75 or 1.75 engineering metres from right boundary', 'unit': 'm'},
        {'name': 'right_impediment', 'kind': 'world_setup',
         'range_or_domain': 'none, moving vehicle, standing vehicle', 'unit': 'category'},
        {'name': 'narrow_lane', 'kind': 'world_setup',
         'range_or_domain': 'reviewed lane dimensions, narrow comparison', 'unit': 'boolean'},
        {'name': 'traffic_speed_context', 'kind': 'world_setup',
         'range_or_domain': 'source-reviewed nearby traffic speed context', 'unit': 'category'},
        {'name': 'left_turn_preparation', 'kind': 'world_setup',
         'range_or_domain': 'source-declared turn preparation or absence', 'unit': 'boolean'},
        {'name': 'target_motion', 'kind': 'world_setup',
         'range_or_domain': 'moving same direction or standing', 'unit': 'category'},
    ]
    template = {'template_id': TEMPLATE, 'law_id': LAW, 'actor': ACTOR,
                'status': 'draft', 'quote': quote,
                'structure': {
                    'law_id': LAW,
                    'activation': {'condition': 'Person operates a bicycle, electric bicycle or electric scooter on a roadway.',
                                   'numeric_conditions': []},
                    'obligation': {'description': 'Ride as near the right side as practicable and exercise due care when passing a standing or same-direction vehicle.',
                                   'type': 'must', 'numeric_conditions': []},
                    'exceptions': [
                        {'source_clause': 'When traveling at a lawful rate of speed commensurate with the speed of any nearby traffic',
                         'description': 'Separately sourced lawful-speed and nearby-traffic context.', 'numeric_conditions': []},
                        {'source_clause': 'When preparing to turn left',
                         'description': 'Original operator turn preparation and intent source.', 'numeric_conditions': []},
                        {'source_clause': 'When doing so would not be safe',
                         'description': 'Right-side impediments and narrow lane examples of 777(2), without an exhaustive safety rule.',
                         'numeric_conditions': []},
                    ],
                    'timing': {'description': 'Preserve original approach, alongside and ahead histories plus right-side placement.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note}
                                              for phrase, note, _ in judgments]},
                'parameter_refs': parameters}
    template_ref = write('template.json', template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(judgments):
        judgment_refs.append(write(f'judgment-{index}.json', {
            'template_id': TEMPLATE, 'phrase': phrase, 'note': note,
            'status': 'draft', 'observable_requirements': {
                'observables': [{'name': channel, 'unit': 'source observation',
                                 'description': note}],
                'context_inputs': [], 'sweep_dimensions': [], 'landmarks': [],
                'recording_needs': [{'name': channel, 'unit': 'original source',
                                     'description': note}],
                'limitations': ['The law supplies no numeric threshold for this judgment; original physical and legal review remain open.']}}))
    binding_ref = write('bindings.json', {
        'cell_id': 'C229023', 'actor': ACTOR, 'status': 'draft',
        'law_refs': [{'template_id': TEMPLATE, 'binding_kind': 'direct'}],
        'context_refs': [], 'fixed_parameters': [],
        'variable_parameters': [dict(item, used_by_laws=[LAW]) for item in parameters]})
    selected = []
    for case in plan['cases']:
        name = case['case_id'].removeprefix(AID + '__')
        config_path = HERE / ('config.json' if name == CASES[0].name else
                              'cases/' + name + '/config.json')
        description = json.loads(config_path.read_text())['case']['recording_description']
        assignments = {
            item['name']: {'kind': item['kind'], 'value': case[item['name']],
                           'unit': item['unit']}
            for item in parameters}
        primary = next((comparison['deliberate_differences'][0]
                        for comparison in plan['comparisons']
                        if comparison['case_ids'][-1] == case['case_id']),
                       'requested_lateral_target_m')
        selected.append({
            'case_id': case['case_id'], 'target_law_id': LAW,
            'target_type': 'boundary_probe', 'status': 'draft',
            'rationale': 'Exact roadway cycle passing with right-side and exception context; original legal judgments remain unresolved.',
            'paired_probe_id': 'cycle_right_side_passing',
            'deliberate_differences': [primary],
            'probe': {'primary_variable': primary,
                      'comparison_or_standard': 'Compare original right-edge/body/traffic histories without adopting a legal cutoff.',
                      'target_value_or_branch': name},
            'variable_assignments': assignments,
            'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
            'recording_description': description,
        })
    first = selected[0]
    baseline = {'case_id': AID + '__baseline', 'target_law_id': None,
                'target_type': 'baseline', 'status': 'draft',
                'rationale': 'Common source-reviewed cycle and target vehicle on roadway with no legal finding.',
                'variable_assignments': first['variable_assignments'],
                'unresolved_judgment_calls': [phrase for phrase, _, _ in judgments],
                'recording_description': first['recording_description']}
    sweeps = [{'sweep_id': 'c229023-7771-' + str(index), 'target_law_id': LAW,
               'judgment_refs': [{'phrase': phrase, 'note': note}],
               'status': 'incomplete',
               'rationale': 'No reviewed original scene or independent legal judgment range; physical selected comparisons remain runnable.',
               'missing_inputs': ['reviewed original roadway and original Native physical capture']}
              for index, (phrase, note, _) in enumerate(judgments)]
    cases_ref = write('cases.json', {'cell_id': 'C229023', 'actor': ACTOR,
                                     'status': 'draft', 'sweep_specs': sweeps,
                                     'cases': [baseline, *selected]})
    write('semantic-index.json', {'format': 'worker-semantic-delivery',
                                  'assignment_id': AID,
                                  'stages': {'relevance_batch': relevance_ref,
                                             'relevance': relevance_ref,
                                             'template': template_ref,
                                             'judgment_observables': judgment_refs,
                                             'bindings': binding_ref,
                                             'cases': cases_ref},
                                  'status': 'source_gated_draft'})
    return len(selected), len(judgments)


if __name__ == '__main__':
    print('canonical selected cases and judgments:', *build())
