"""Author draft canonical stage proposals from exact law and selected cases."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'proposals'
LAW_ID = 'NRS-484B-413-1'
TEMPLATE_ID = LAW_ID + '@motor_vehicle_driver'


def write(name, value):
    path = OUT / (name + '.json')
    path.write_text(json.dumps(value, indent=2) + '\n')
    return {'path': str(path.relative_to(HERE)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
    law = assignment['law']
    original_cases = json.loads((OUT / 'cases.json').read_text())
    selected = [deepcopy(case) for case in original_cases['cases']
                if case['target_type'] != 'baseline']
    relevance = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'],
                 'status': 'draft', 'relevant_laws': [{'law_id': LAW_ID,
                 'quote': law['text'], 'applies_to': [assignment['actor']],
                 'relevance_type': 'specific_match', 'confidence': 'high',
                 'notes': 'Frozen turn/other-vehicle cell; pedestrian and vehicle conditional branches are separately observed.'}],
                 'borderline_excluded': []}
    refs = {'relevance_batch': write('relevance_batch', relevance),
            'relevance': write('relevance', relevance)}
    phrases = [
        ('reasonable safety', 'Original turn/body gap and context are retained; no legal safety cutoff.'),
        ('clearly audible signal', 'Listener PCM and actuator request are separate observations; audibility requires physical review.'),
        ('any pedestrian may be affected', 'Retain original pedestrian body path and turn corridor; effect remains a judgment.'),
        ('appropriate signal', 'Retain Native indicator readback or original hand pose and source pixels; appropriateness remains unresolved.'),
        ('any other vehicle may be affected', 'Retain original vehicle body path and turn corridor; effect remains a judgment.'),
    ]
    parameters = [
        ('affected_vehicle_clearance_path_m', 'world_setup', 'engineering scalar s: affected vehicle offset (max(0,s),s) m at -1, 2 or 5; no legal safety cutoff'),
        ('hand_signal_pose', 'controller', 'none or selected left-arm original Native bone pose'),
        ('horn_actuation', 'controller', 'none or identified relay request with separate listener PCM'),
        ('listener_route_lateral_offset_m', 'world_setup', 'engineering listener sidewalk offsets 2, 4 or 6 m; no legal audibility cutoff'),
        ('pedestrian_may_be_affected', 'world_setup', 'planned pedestrian route and measured body proximity; actual effect unresolved'),
        ('turn_indicator_state', 'controller', 'off or left with Native readback'),
        ('vehicle_may_be_affected', 'world_setup', 'planned other-vehicle route and measured body proximity; actual effect unresolved'),
    ]
    template = {'template_id': TEMPLATE_ID, 'law_id': LAW_ID, 'actor': assignment['actor'],
                'status': 'draft', 'quote': law['text'],
                'structure': {'law_id': LAW_ID,
                    'activation': {'condition': 'Driver turns vehicle from a direct course on a highway.',
                                   'numeric_conditions': []},
                    'obligation': {'type': 'must_not',
                                   'description': 'Do not turn until reasonable safety; when a pedestrian may be affected sound a clearly audible horn, and when another vehicle may be affected give an appropriate signal.',
                                   'numeric_conditions': []},
                    'exceptions': [],
                    'timing': {'description': 'Safety and conditional signals precede the turn from a direct course.',
                               'numeric_conditions': []},
                    'judgment_calls_needed': [{'phrase': phrase, 'note': note} for phrase, note in phrases]},
                'parameter_refs': [{'name': name, 'kind': kind, 'range_or_domain': domain}
                                   for name, kind, domain in parameters]}
    refs['template'] = write('template', template)
    dimensions = [
        ('minimum_sampled_surface_gap_m', 'm',
         'Minimum original-frame ego-to-participant body surface gap during the turn.'),
        ('pre_turn_listener_audio_rms', 'normalized PCM',
         'Original listener PCM amplitude before measured turn onset; physical audibility remains unresolved.'),
        ('pedestrian_minimum_surface_gap_m', 'm',
         'Minimum original-frame body surface gap to the identified pedestrian.'),
        ('pre_turn_signal_frames', 'frames',
         'Original Native indicator or hand-pose readback frames before measured turn onset.'),
        ('vehicle_minimum_surface_gap_m', 'm',
         'Minimum original-frame body surface gap to the identified other vehicle.'),
    ]
    judgment_refs = []
    for index, (phrase, note) in enumerate(phrases, 1):
        dimension_name, dimension_unit, dimension_description = dimensions[index - 1]
        requirement = {'observables': [{'name': 'turn_signal_observation', 'unit': 'structured',
                                        'description': 'Original turn, body, signal and listener status retained at 20 Hz.'}],
                       'context_inputs': [],
                       'sweep_dimensions': [{'name': dimension_name, 'unit': dimension_unit,
                                            'description': dimension_description}],
                       'landmarks': [],
                       'recording_needs': [{'name': 'turn_signal_observation', 'unit': 'structured',
                                            'description': 'Original case-specific turn and conditional signal observation.'}],
                       'limitations': ['Diagnostic streams do not establish physical visibility, audibility, affected-party status or legal judgment.']}
        if phrase == 'clearly audible signal':
            requirement['sweep_dimensions'].append({
                'name': 'listener_route_lateral_offset_m', 'unit': 'm',
                'description': 'Requested Native route-relative sidewalk listener position; original PCM remains separately measured.'})
        if phrase == 'reasonable safety':
            requirement['sweep_dimensions'].append({
                'name': 'affected_vehicle_clearance_path_m', 'unit': 'm',
                'description': 'Engineering scalar for the exact affected-vehicle placement path; original turn-onset and minimum body gaps remain separate measurements.'})
        judgment_refs.append(write('judgment_' + str(index), {'template_id': TEMPLATE_ID,
                            'phrase': phrase, 'note': note, 'status': 'draft',
                            'observable_requirements': requirement}))
    refs['judgment_observables'] = judgment_refs
    binding = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
               'established_contexts': ['intersection layout', 'turn maneuver', 'other_vehicle control'],
               'law_refs': [{'template_id': TEMPLATE_ID, 'binding_kind': 'direct'}],
               'context_refs': [],
               'fixed_parameters': [{'name': 'cell_layout', 'value': 'intersection', 'rationale': 'Frozen catalog layout'},
                                    {'name': 'cell_maneuver', 'value': 'turn', 'rationale': 'Frozen catalog maneuver'},
                                    {'name': 'cell_control', 'value': 'other_vehicle', 'rationale': 'Frozen catalog control'}],
               'variable_parameters': [{'name': name, 'kind': kind, 'range_or_domain': domain,
                                        'used_by_laws': [LAW_ID]} for name, kind, domain in parameters]}
    refs['bindings'] = write('bindings', binding)
    defaults = {'affected_vehicle_clearance_path_m': {'kind': 'world_setup', 'value': 'not_selected'},
                'hand_signal_pose': {'kind': 'controller', 'value': 'none'},
                'horn_actuation': {'kind': 'controller', 'value': 'none'},
                'listener_route_lateral_offset_m': {'kind': 'world_setup', 'value': 'not_selected'},
                'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False},
                'turn_indicator_state': {'kind': 'controller', 'value': 'off'},
                'vehicle_may_be_affected': {'kind': 'world_setup', 'value': False}}
    pair = {
        'vehicle_left_indicator': ('vehicle_indicator', ['turn_indicator_state']),
        'vehicle_no_indicator': ('vehicle_indicator', ['turn_indicator_state']),
        'clearance_wide': ('reasonable_safety_clearance', ['affected_vehicle_clearance_path_m']),
        'clearance_narrow': ('reasonable_safety_clearance', ['affected_vehicle_clearance_path_m']),
        'clearance_mid': ('reasonable_safety_clearance', ['affected_vehicle_clearance_path_m']),
        'ped_horn_audio': ('pedestrian_horn_audio', ['horn_actuation']),
        'ped_horn_listener_2m': ('pedestrian_listener_distance', ['listener_route_lateral_offset_m']),
        'ped_horn_listener_4m': ('pedestrian_listener_distance', ['listener_route_lateral_offset_m']),
        'ped_horn_listener_6m': ('pedestrian_listener_distance', ['listener_route_lateral_offset_m']),
        'ped_no_horn_audio': ('pedestrian_horn_audio', ['horn_actuation']),
        'both_signals': ('both_affected_conjunction', ['horn_actuation']),
        'both_indicator_only': ('both_affected_conjunction', ['horn_actuation']),
        'vehicle_hand_signal': ('vehicle_signal_alternative', ['turn_indicator_state', 'hand_signal_pose']),
    }
    for case in selected:
        suffix = case['case_id'][len(HERE.name) + 2:]
        original = case['variable_assignments']
        case['variable_assignments'] = dict(deepcopy(defaults),
            **{name: value for name, value in original.items()
               if name != 'affected_vehicle_exit_offset_m'})
        paired, changed = pair[suffix]
        case['paired_probe_id'] = paired
        case['deliberate_differences'] = changed
        case['probe'] = {'primary_variable': changed[0],
                         'comparison_or_standard': 'controlled original-source contrast; legal judgment unresolved',
                         'target_value_or_branch': suffix}
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in phrases]
        if suffix in ('clearance_narrow', 'clearance_mid', 'clearance_wide'):
            scalar = {'clearance_narrow': -1, 'clearance_mid': 2,
                      'clearance_wide': 5}[suffix]
            expected = [max(0, scalar), scalar] if scalar >= 0 else [0, scalar]
            if original['affected_vehicle_exit_offset_m']['value'] != expected:
                raise ValueError('Clearance scalar path differs from exact construction')
            case['variable_assignments']['affected_vehicle_clearance_path_m'] = {
                'kind': 'world_setup', 'value': scalar}
            case['deliberate_differences'] = ['affected_vehicle_clearance_path_m']
            case['probe']['primary_variable'] = 'affected_vehicle_clearance_path_m'
    safety_order = {'clearance_narrow': 0, 'clearance_wide': 1, 'clearance_mid': 2}
    listener_order = {'ped_horn_listener_2m': 0, 'ped_horn_listener_6m': 1,
                      'ped_horn_listener_4m': 2}
    selected.sort(key=lambda case: (0, safety_order[case['case_id'][len(HERE.name) + 2:]])
                  if case['case_id'][len(HERE.name) + 2:] in safety_order else
                  (1, listener_order[case['case_id'][len(HERE.name) + 2:]])
                  if case['case_id'][len(HERE.name) + 2:] in listener_order else (-1, 0))
    safety_cases = [case for case in selected if case['case_id'][len(HERE.name) + 2:] in safety_order]
    if len(safety_cases) != 3:
        raise ValueError('Three exact safety sweep cases required')
    safety_spec = {'sweep_id': 'turn_clearance_path', 'target_law_id': LAW_ID,
        'judgment_refs': [{'phrase': phrases[0][0], 'note': phrases[0][1]}],
        'rationale': 'Finite -1/2/5 m engineering placement path with original turn-onset and minimum body gaps retained; no legal safety cutoff.',
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{'variable': 'affected_vehicle_clearance_path_m',
            'observable': 'affected_vehicle_clearance_path_m', 'unit': 'm',
            'min': -1, 'max': 5, 'spacing': 3,
            'range_rationale': 'Three exact affected-vehicle placements follow (max(0,s),s) meters from the Native exit.',
            'spacing_rationale': 'Three-meter scalar spacing gives distinct original turn-onset body gaps while retaining the minimum-gap tie at the middle point.',
            'feasibility_evidence': 'Exact Native runner constructions and primary/fallback CPU compatibility receipts for all three placements; actual map feasibility remains for local Native preflight.',
            'measurement': {'method': 'Native requested offset and original participant-body/turn-motion frame join',
                            'time_window': 'original turn frames', 'statistic': 'first'}}],
        'landmarks': [], 'recording_description': deepcopy(safety_cases[0]['recording_description'])}
    safety_spec['spec_version'] = hashlib.sha256(json.dumps(safety_spec, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    safety_spec['planned_case_count'] = 3
    safety_spec['selection_order'] = [case['case_id'] for case in safety_cases]
    for case in safety_cases:
        case['target_type'] = 'judgment_sweep'
        case['sweep_id'] = safety_spec['sweep_id']
        case['sweep_spec_version'] = safety_spec['spec_version']
        case['sweep_point'] = {'affected_vehicle_clearance_path_m':
            float(case['variable_assignments']['affected_vehicle_clearance_path_m']['value'])}
    listener_cases = [case for case in selected if case['case_id'][len(HERE.name) + 2:] in listener_order]
    if len(listener_cases) != 3:
        raise ValueError('Three exact listener sweep cases required')
    listener_spec = {'sweep_id': 'turn_listener_distance', 'target_law_id': LAW_ID,
        'judgment_refs': [{'phrase': phrases[1][0], 'note': phrases[1][1]}],
        'rationale': 'Finite 2/4/6 m engineering listener-distance grid with original PCM retained; no audibility cutoff.',
        'status': 'complete', 'mode': 'one_dimensional',
        'axes': [{'variable': 'listener_route_lateral_offset_m',
            'observable': 'listener_route_lateral_offset_m', 'unit': 'm',
            'min': 2, 'max': 6, 'spacing': 2,
            'range_rationale': 'Three route-relative candidate sidewalk points authored and original-shaped body gaps audited.',
            'spacing_rationale': 'Two-meter spacing yields distinct sampled diagnostic body gaps without a legal threshold.',
            'feasibility_evidence': 'listener_sweep_placement.py tests Native waypoint resolution and rejects absent sidewalks; actual map feasibility remains for local Native preflight.',
            'measurement': {'method': 'Native requested offset and original participant transform/PCM join',
                            'time_window': 'original pre-turn frames', 'statistic': 'first'}}],
        'landmarks': [], 'recording_description': deepcopy(listener_cases[0]['recording_description'])}
    listener_spec['spec_version'] = hashlib.sha256(json.dumps(listener_spec, sort_keys=True,
        separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    listener_spec['planned_case_count'] = 3
    listener_spec['selection_order'] = [case['case_id'] for case in listener_cases]
    for case in listener_cases:
        suffix = case['case_id'][len(HERE.name) + 2:]
        case['target_type'] = 'judgment_sweep'
        case['sweep_id'] = listener_spec['sweep_id']
        case['sweep_spec_version'] = listener_spec['spec_version']
        case['sweep_point'] = {'listener_route_lateral_offset_m':
            float(suffix.rsplit('_', 1)[-1][:-1])}
    baseline = {'case_id': HERE.name + '__semantic_baseline', 'target_law_id': LAW_ID,
                'target_type': 'baseline', 'rationale': 'Neutral semantic comparison anchor only; no additional recording or manifest entry.',
                'variable_assignments': deepcopy(defaults),
                'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
                'recording_description': deepcopy(selected[0]['recording_description'])}
    missing = ['Source-backed finite affected-pedestrian and affected-vehicle status sweeps with controlled context',
               'A listener PCM level contrast across the three distance points if feasible; diagnostic PCM is currently fixed',
               'Original physical visibility, audibility and Native feasibility review without invented legal cutoffs']
    sweep = {'sweep_id': 'turn_remaining_qualitative_observables', 'target_law_id': LAW_ID,
             'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in phrases if phrase not in ('clearly audible signal', 'reasonable safety')],
             'status': 'incomplete', 'rationale': 'Thirteen selected points include three measured clearance levels and three signal mechanisms; affected-party and listener PCM level sweeps remain incomplete.',
             'missing_inputs': missing}
    cases = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
             'cases': [baseline] + selected, 'sweep_specs': [safety_spec, listener_spec, sweep],
             'sweeps_expanded': True}
    refs['cases'] = write('cases', cases)
    write('semantic-index', {'format': 'worker-semantic-delivery',
                             'assignment_id': HERE.name, 'stages': refs})


if __name__ == '__main__':
    main()
