"""Build draft semantic stages with a finite three-point speed judgment sweep.

The authored grid is for physical coverage, not a legal speed threshold.
"""
import hashlib
import json
from pathlib import Path
from batch_pipeline.store import digest
from batch_pipeline.sweeps import grid

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
LAW = 'NRS-484B-600-1a'
ACTOR = 'motor_vehicle_driver'
CELL = 'C179789'
SOURCE = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
TEXT = SOURCE['law']['text']
QUOTE = 'A rate of speed greater than is reasonable or proper, having due regard for the traffic, surface and width of the highway, the weather and other highway conditions.'
PHRASE = 'reasonable or proper'
SUFFIXES = ('dry_4mps', 'dry_open_traffic', 'dry_6mps',
            'wet_same_traffic', 'narrow_same_traffic', 'dense_traffic',
            'low_visibility', 'ice_or_snow')
PARAMETERS = [
    ('requested_speed_mps', 'controller', 'authored finite ego speed target, m/s'),
    ('ego_speed_mps', 'subject_behavior', 'original sampled ego speed, m/s'),
    ('surface_condition', 'world_setup', 'source reviewed dry, wet, or ice/snow roadway'),
    ('lane_width_target_m', 'world_setup', 'sourced Native lane width, m'),
    ('lead_gap_target_m', 'controller', 'authored complete-body lead gap range, m'),
    ('weather_profile', 'world_setup', 'source bound Native weather profile'),
]


def write(name, value):
    path = ROOT / 'proposals' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def assignments(suffix):
    weather = 'dry'
    surface = 'dry'
    width = 3.5
    gap = 20
    if suffix == 'wet_same_traffic':
        weather, surface = 'rain', 'wet'
    elif suffix == 'narrow_same_traffic':
        width = 2.7
    elif suffix == 'dense_traffic':
        gap = 8
    elif suffix == 'low_visibility':
        weather = 'fog'
    elif suffix == 'ice_or_snow':
        weather, surface = 'cold_precipitation', 'ice_or_snow'
    speed = {'dry_4mps': 4, 'dry_6mps': 6}.get(suffix, 8)
    values = {'requested_speed_mps': speed, 'ego_speed_mps': None,
              'surface_condition': surface, 'lane_width_target_m': width,
              'lead_gap_target_m': gap, 'weather_profile': weather}
    units = {'requested_speed_mps': 'm/s', 'ego_speed_mps': 'm/s',
             'surface_condition': 'categorical', 'lane_width_target_m': 'm',
             'lead_gap_target_m': 'm', 'weather_profile': 'categorical'}
    return {name: {'kind': kind, 'value': values[name], 'unit': units[name]}
            for name, kind, _ in PARAMETERS}


def main():
    if QUOTE not in TEXT:
        raise ValueError('Exact source quote changed')
    relevance = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
                 'relevant_laws': [{'law_id': LAW, 'quote': QUOTE,
                                    'applies_to': [ACTOR],
                                    'relevance_type': 'paved-road speed with traffic and road conditions',
                                    'confidence': 'high',
                                    'notes': 'The condition comparisons are selected; reasonable-or-proper judgment remains unresolved.'}],
                 'borderline_excluded': []}
    template = {'template_id': LAW + '@' + ACTOR, 'law_id': LAW,
                'actor': ACTOR, 'status': 'draft', 'quote': QUOTE,
                'structure': {'law_id': LAW,
                              'activation': {'condition': 'person drives or operates a vehicle',
                                             'numeric_conditions': []},
                              'obligation': {'description': 'speed must account for traffic, surface, width, weather and other highway conditions',
                                             'type': 'must_not', 'numeric_conditions': []},
                              'exceptions': [],
                              'timing': {'description': 'continuous driving interval with frame-specific changing conditions',
                                         'numeric_conditions': []},
                              'judgment_calls_needed': [{'phrase': PHRASE,
                                                         'note': 'Statute provides no numeric speed threshold; external judgment remains separate from diagnostic stopping distance.'}]},
                'parameter_refs': [{'name': name, 'kind': kind,
                                    'range_or_domain': domain}
                                   for name, kind, domain in PARAMETERS]}
    needs = {'observables': [
                 {'name': name, 'unit': unit, 'description': description}
                 for name, unit, description in (
                     ('ego_speed_mps', 'm/s', 'original sampled ego speed'),
                     ('longitudinal_body_gap_m', 'm', 'original complete-body lead traffic gap'),
                     ('lane_width_m', 'm', 'original Native lane width'),
                     ('precipitation_percent', 'percent', 'original Native weather readback'),
                     ('sight_distance_m', 'm', 'first obstruction ray distance; not optical visibility'))],
             'context_inputs': [{'name': 'road_context', 'unit': 'structured record',
                                 'description': 'source-hashed roadway, traffic and weather context'}],
             'sweep_dimensions': [{'name': 'ego_speed_mps', 'unit': 'm/s',
                                   'description': 'sampled physical ego speed across an authored numeric grid'}],
             'landmarks': [],
             'recording_needs': [{'name': 'ego_speed_mps', 'unit': 'm/s',
                                  'description': 'original frame-specific speed stream'},
                                 {'name': 'longitudinal_body_gap_m', 'unit': 'm',
                                  'description': 'original surrounding traffic gap stream'},
                                 {'name': 'lane_width_m', 'unit': 'm',
                                  'description': 'original roadway width stream'},
                                 {'name': 'sight_distance_m', 'unit': 'm',
                                  'description': 'original first-obstruction ray stream'}],
             'limitations': ['The law leaves reasonable or proper to independent judgment; no speed value here is a statutory threshold.',
                             'Native weather and first-obstruction ray do not prove roadway surface or optical visibility.']}
    judgment = {'template_id': template['template_id'], 'phrase': PHRASE,
                'note': template['structure']['judgment_calls_needed'][0]['note'],
                'status': 'draft', 'observable_requirements': needs}
    binding = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft',
               'established_contexts': ['Paved-road travel with another vehicle; surface, width and weather require original source review.'],
               'law_refs': [{'template_id': template['template_id'], 'binding_kind': 'direct'}],
               'context_refs': [], 'fixed_parameters': [],
               'variable_parameters': [{'name': name, 'kind': kind,
                                        'range_or_domain': domain, 'used_by_laws': [LAW]}
                                       for name, kind, domain in PARAMETERS]}
    cases = []
    baseline_description = json.loads((ROOT / 'config.json').read_text())['recording_description']
    cases.append({'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
                  'target_type': 'baseline',
                  'rationale': 'Shared condition and measurement reference; not a selected recording.',
                  'variable_assignments': assignments('dry_open_traffic'),
                  'unresolved_judgment_calls': [PHRASE],
                  'recording_description': baseline_description})
    primary = {'dry_4mps': 'requested_speed_mps',
               'dry_6mps': 'requested_speed_mps',
               'dry_open_traffic': 'requested_speed_mps',
               'wet_same_traffic': 'surface_condition',
               'narrow_same_traffic': 'lane_width_target_m',
               'dense_traffic': 'lead_gap_target_m',
               'low_visibility': 'weather_profile',
               'ice_or_snow': 'surface_condition'}
    spec = {'sweep_id': 'reasonable_speed_grid', 'target_law_id': LAW,
            'judgment_refs': [{'phrase': PHRASE, 'note': judgment['note']}],
            'status': 'complete', 'mode': 'one_dimensional',
            'rationale': 'Finite 4, 6 and 8 m/s authored speed targets on the same dry road and traffic; measured ego speed and independent judgment remain separate.',
            'axes': [{'variable': 'requested_speed_mps', 'observable': 'ego_speed_mps',
                      'unit': 'm/s', 'min': 4, 'max': 8, 'spacing': 2,
                      'range_rationale': 'Three feasible diagnostic controller setpoints below, near and above the fixed 7 m/s lead target; no legal boundary is implied.',
                      'spacing_rationale': '2 m/s separates the three authored controller targets for later original speed measurement.',
                      'feasibility_evidence': 'Exact source-bound software constructions and CPU physical-preparation fixtures; Native realization remains unverified.',
                      'measurement': {'method': 'original Native ego velocity samples',
                                      'time_window': 'entire captured interval',
                                      'statistic': 'max'}}],
            'landmarks': [],
            'variable_assignments': assignments('dry_open_traffic'),
            'recording_description': baseline_description}
    spec['spec_version'] = digest(spec)
    spec['planned_case_count'] = len(grid(spec))
    spec['selection_order'] = [ASSIGNMENT + '__' + suffix for suffix in
                               ('dry_4mps', 'dry_open_traffic', 'dry_6mps')]
    for suffix in SUFFIXES:
        construction = ROOT / ('construction.json' if suffix == 'dry_open_traffic' else
                               'cases/' + suffix + '-construction.json')
        packet = json.loads(construction.read_text())
        variable = primary[suffix]
        speed_member = suffix in ('dry_4mps', 'dry_open_traffic', 'dry_6mps')
        case = {'case_id': packet['case_id'], 'target_law_id': LAW,
                      'target_type': 'judgment_sweep',
                      'rationale': ('Finite authored speed-grid point; no legal outcome assigned.' if speed_member else
                                    'Source-bound condition comparison at a fixed authored speed; no legal outcome assigned.'),
                      'variable_assignments': assignments(suffix),
                      'unresolved_judgment_calls': [PHRASE],
                      'recording_description': packet['recording_description'],
                      'paired_probe_id': ('reasonable_speed_grid' if speed_member else 'road_speed_conditions'),
                      'deliberate_differences': (['requested_speed_mps'] if speed_member else
                                                 ['surface_condition', 'lane_width_target_m',
                                                  'lead_gap_target_m', 'weather_profile']),
                      'probe': {'primary_variable': variable,
                                'comparison_or_standard': 'same sourced roadway/traffic controls except declared condition change',
                                'target_value_or_branch': suffix}}
        if speed_member:
            point = {'requested_speed_mps': assignments(suffix)['requested_speed_mps']['value']}
            case.update({'sweep_id': spec['sweep_id'], 'sweep_spec_version': spec['spec_version'],
                         'sweep_point': point,
                         'selection_rank': spec['selection_order'].index(packet['case_id']),
                         'judgment_refs': spec['judgment_refs'],
                         'sweep_measurements': [{'variable': 'requested_speed_mps',
                                                 'observable': 'ego_speed_mps', 'unit': 'm/s',
                                                 'measurement': spec['axes'][0]['measurement']}]})
            case['probe']['comparison_or_standard'] = 'physical speed coverage; legal judgment unresolved'
            case['probe']['target_value_or_branch'] = point
        cases.append(case)
    proposal = {'cell_id': CELL, 'actor': ACTOR, 'status': 'draft', 'cases': cases,
                'sweep_specs': [spec], 'sweeps_expanded': True}
    refs = {'relevance_batch': write('relevance.json', relevance),
            'relevance': None,
            'template': write('template.json', template),
            'judgment_observables': [write('judgment-observables.json', judgment)],
            'bindings': write('bindings.json', binding),
            'cases': write('cases.json', proposal)}
    refs['relevance'] = refs['relevance_batch']
    index = {'assignment_id': ASSIGNMENT, 'format': 'worker-semantic-delivery',
             'stages': refs}
    write('semantic-index.json', index)
    print(json.dumps({'stage_count': 6, 'selected_cases': len(SUFFIXES),
                      'sweep_complete': True}, indent=2))


if __name__ == '__main__':
    main()
