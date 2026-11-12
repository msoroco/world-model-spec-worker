"""Saved-only source analysis for the first inoperative-signal median case.

This measures complete-body entry and right-side geometry. Approximate timing,
subsection-4 applicability and legal priority remain for independent review.
"""
import argparse
import hashlib
import json
from pathlib import Path

from simultaneous_entries import analyze


PRIMARY = 'testing__C125697__NRS-484B-250-2__motor_vehicle_driver__operative_signal'
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_crossing_context(context):
    return {'native_map_id': context['native_map_id'],
            'intersection_id': context['intersection_id'],
            'ego_highway_id': context['ego_highway_id'],
            'other_highway_id': context['other_highway_id'],
            'same_statutory_crossing': context['same_statutory_crossing'],
            'crossing_geometry_source': context['crossing_geometry_source'],
            'median_spacing_source': context['median_spacing_source']}


def measure_entry_timing(report):
    return {'first_complete_body_entry': report['first_body_entry'],
            'absolute_difference_s': report['absolute_entry_time_difference_s'],
            'approximately_same_time_judgment': 'unresolved'}


def measure_relative_side(report):
    return {'other_spatially_right_of_ego_approach':
            report['other_spatially_right_of_ego_approach'],
            'signed_lateral_offset_m': report['other_right_signed_cross_m']}


def measure_signal_context(context, history):
    if context.get('official_device_operating') is not True:
        raise ValueError('Operative device context required')
    if not history or any(row.get('governing_signal_state') != 'Red' or
                          not isinstance(row.get('entrance_signal_states'), list) or
                          len(row['entrance_signal_states']) < 2 or
                          [head.get('state') for head in row['entrance_signal_states']] !=
                          ['Red', 'Green'] + ['Red'] * (len(row['entrance_signal_states']) - 2)
                          for row in history):
        raise ValueError('Inventoried entrance heads must be operative Red/Green at original frames')
    first_ids = [head.get('actor_id') for head in history[0]['entrance_signal_states']]
    if (any(identifier is None for identifier in first_ids) or
            len(set(first_ids)) != len(first_ids) or
            any([head.get('actor_id') for head in row['entrance_signal_states']] != first_ids
                for row in history)):
        raise ValueError('Stable distinct entrance head identities required')
    return {'captured_entrance_head_count': len(first_ids),
            'captured_entrance_head_ids': first_ids,
            'all_sampled_states_operative': True,
            'ego_governing_state': 'Red', 'other_governing_state': 'Green',
            'all_entrances_source': context['all_entrances_source'],
            'signal_governance_source': context['signal_governance_source'],
            'signal_head_video_source': context['signal_head_video_source'],
            'official_device_exclusion_judgment': 'unresolved',
            'subsection_4_judgment': 'unresolved'}


def measure_opposite_turn_context(context):
    if context.get('opposite_approach_with_left_turn') is not False:
        raise ValueError('First case must retain non-opposite approach setup')
    return {'opposite_approach_with_left_turn_setup': False,
            'exception_judgment': 'unresolved; comparison case required'}


def measure_yield_observation(report, controls):
    samples = report['samples']
    if (len(controls) != len(samples) or
            any(row.get('frame') != sample['frame'] or
                row.get('time_s') != sample['time_s'] or
                type(row.get('ego_held')) is not bool
                for row, sample in zip(controls, samples))):
        raise ValueError('Original controller history does not join source frames')
    return {'ego_hold_frames': [row['frame'] for row in controls if row['ego_held']],
            'observed_control_samples': len(controls),
            'legal_yield_judgment': 'unresolved'}


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt and output')
    required = ('config.json', 'junction_context.json', 'crossing_history.jsonl',
                'controller_history.jsonl',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl', *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    if (config.get('selected_case_id') != PRIMARY or
            config.get('signal_mode') != 'operative_ego_red_other_green' or
            config.get('law_id') != 'NRS-484B-250-2' or
            config.get('cell_id') != 'C125697' or
            config.get('actor') != 'motor_vehicle_driver' or
            not isinstance(config.get('recording_description'), dict)):
        raise ValueError('Exact first C125697 Off-state case configuration required')
    report = analyze(attempt)
    context = json.loads((attempt / 'junction_context.json').read_text())
    if context.get('physical_acceptance_claimed') is not False:
        raise ValueError('Source context cannot claim physical acceptance')
    if not all(report['first_body_entry'].values()):
        raise ValueError('Both complete-body entries required')
    history = [json.loads(row) for row in (attempt / 'crossing_history.jsonl').read_text().splitlines()]
    controls = [json.loads(row) for row in (attempt / 'controller_history.jsonl').read_text().splitlines()]
    measured = {
        'crossing_identity': ('measure_crossing_context', measure_crossing_context(context),
                              ['junction_context.json']),
        'entry_timing': ('measure_entry_timing', measure_entry_timing(report),
                         ['crossing_history.jsonl', 'video_frames.jsonl', 'junction_context.json']),
        'relative_right_side': ('measure_relative_side', measure_relative_side(report),
                                ['crossing_history.jsonl', 'video_frames.jsonl', 'junction_context.json']),
        'device_qualification_context': ('measure_signal_context',
                                         measure_signal_context(context, history),
                                         ['junction_context.json', 'crossing_history.jsonl']),
        'opposite_left_turn_context': ('measure_opposite_turn_context',
                                       measure_opposite_turn_context(context),
                                       ['junction_context.json']),
        'yield_observation': ('measure_yield_observation',
                              measure_yield_observation(report, controls),
                              ['controller_history.jsonl', 'crossing_history.jsonl',
                               'video_frames.jsonl', 'junction_context.json']),
    }
    measurements = {key: {'method': method, 'value': value,
                          'sources': {source: sha(attempt / source) for source in sources}}
                    for key, (method, value, sources) in measured.items()}
    channels = attempt / 'channels'
    channels.mkdir()
    measurement = {
        'method': 'first complete Native body intersection with sourced median crossing',
        'first_body_entry': report['first_body_entry'],
        'absolute_entry_time_difference_s': report['absolute_entry_time_difference_s'],
        'other_spatially_right_of_ego_approach': report['other_spatially_right_of_ego_approach'],
        'other_right_signed_cross_m': report['other_right_signed_cross_m'],
        'all_entrances_source': context['all_entrances_source'],
        'signal_governance_source': context['signal_governance_source'],
        'median_spacing_source': context['median_spacing_source'],
        'approximately_same_time_judgment': 'unresolved',
        'official_device_subsection_4_judgment': 'unresolved',
        'right_of_way_judgment': 'unresolved',
        'source_hashes': report['sources'],
    }
    (channels / 'entry_context.json').write_text(json.dumps(
        {'entry_context': measurement}, indent=2, allow_nan=False) + '\n')
    (channels / 'entry_timing.jsonl').write_text(''.join(
        json.dumps({'time_s': row['time_s'], 'value': {
            'frame': row['frame'],
            'ego_body_in_crossing': row['ego']['body_in_crossing'],
            'other_body_in_crossing': row['other']['body_in_crossing']}},
            allow_nan=False) + '\n' for row in report['samples']))
    result = {
        'case_id': PRIMARY,
        'measured_values': {'absolute_entry_time_difference_s': report['absolute_entry_time_difference_s'],
                            'other_spatially_right_of_ego_approach': report['other_spatially_right_of_ego_approach']},
        'target_checks': [{'target': 'both_bodies_enter_sourced_median_crossing',
                           'requested': True, 'measured': True,
                           'method': measurement['method'], 'tolerance': 0,
                           'matched': True, 'physical_cause_confirmed': False,
                           'cause_evidence': ['junction_context.json', 'crossing_history.jsonl',
                                              'video_frames.jsonl']}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Saved original-source entry analysis; Native and legal review pending',
        'physical_failure_flags': ['median crossing identity, device qualification, '
                                   'approximate timing and yielding remain unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': list(CAMERAS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [{'name': 'entry_context', 'unit': 'structured record',
                                'reference': 'channels/entry_context.json'},
                               {'name': 'entry_timing', 'unit': 'structured record',
                                'reference': 'channels/entry_timing.jsonl'}],
        'source_evidence_hashes': {**report['sources'],
                                   'controller_history.jsonl': sha(attempt / 'controller_history.jsonl'),
                                   'trace.jsonl': sha(attempt / 'trace.jsonl')},
        'capture_evidence_sha256': sha(attempt / 'capture/evidence.jsonl'),
        'realized_observables': {},
    }
    result = physical_result(attempt, result)
    write_result(attempt, result)
    output.write_text(json.dumps({'format': 'worker-c125697-median-entry-saved-analysis',
                                  'case_id': PRIMARY, 'measurement': measurement,
                                  'measurements': measurements,
                                  'physical_acceptance_claimed': False}, indent=2,
                                 allow_nan=False) + '\n')
    return measurement


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': PRIMARY,
                      'absolute_entry_time_difference_s': report['absolute_entry_time_difference_s'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
