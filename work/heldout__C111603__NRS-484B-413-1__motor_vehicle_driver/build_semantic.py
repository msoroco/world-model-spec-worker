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
        ('affected_vehicle_exit_offset_m', 'world_setup', 'source-backed selected affected-vehicle exit placement in meters'),
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
    defaults = {'affected_vehicle_exit_offset_m': {'kind': 'world_setup', 'value': [0, 0]},
                'hand_signal_pose': {'kind': 'controller', 'value': 'none'},
                'horn_actuation': {'kind': 'controller', 'value': 'none'},
                'listener_route_lateral_offset_m': {'kind': 'world_setup', 'value': 'not_selected'},
                'pedestrian_may_be_affected': {'kind': 'world_setup', 'value': False},
                'turn_indicator_state': {'kind': 'controller', 'value': 'off'},
                'vehicle_may_be_affected': {'kind': 'world_setup', 'value': False}}
    pair = {
        'vehicle_left_indicator': ('vehicle_indicator', ['turn_indicator_state']),
        'vehicle_no_indicator': ('vehicle_indicator', ['turn_indicator_state']),
        'clearance_wide': ('reasonable_safety_clearance', ['affected_vehicle_exit_offset_m']),
        'clearance_narrow': ('reasonable_safety_clearance', ['affected_vehicle_exit_offset_m']),
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
        case['variable_assignments'] = dict(deepcopy(defaults), **original)
        paired, changed = pair[suffix]
        case['paired_probe_id'] = paired
        case['deliberate_differences'] = changed
        case['probe'] = {'primary_variable': changed[0],
                         'comparison_or_standard': 'controlled original-source contrast; legal judgment unresolved',
                         'target_value_or_branch': suffix}
        case['unresolved_judgment_calls'] = [phrase for phrase, _ in phrases]
    baseline = {'case_id': HERE.name + '__semantic_baseline', 'target_law_id': LAW_ID,
                'target_type': 'baseline', 'rationale': 'Neutral semantic comparison anchor only; no additional recording or manifest entry.',
                'variable_assignments': deepcopy(defaults),
                'unresolved_judgment_calls': [phrase for phrase, _ in phrases],
                'recording_description': deepcopy(selected[0]['recording_description'])}
    missing = ['Verified Native feasible variation across turn clearance, listener audibility and signal visibility',
               'Source-bound physical affected-party review and no invented legal cutoffs',
               'Additional exact sweep cases only after a measured feasible range is established']
    sweep = {'sweep_id': 'turn_qualitative_observables', 'target_law_id': LAW_ID,
             'judgment_refs': [{'phrase': phrase, 'note': note} for phrase, note in phrases],
             'status': 'incomplete', 'rationale': 'The nine selected controlled points do not yet span the five qualitative judgments.',
             'missing_inputs': missing}
    cases = {'cell_id': assignment['cell_id'], 'actor': assignment['actor'], 'status': 'draft',
             'cases': [baseline] + selected, 'sweep_specs': [sweep],
             'sweeps_expanded': True}
    refs['cases'] = write('cases', cases)
    write('semantic-index', {'format': 'worker-semantic-delivery',
                             'assignment_id': HERE.name, 'stages': refs})


if __name__ == '__main__':
    main()
