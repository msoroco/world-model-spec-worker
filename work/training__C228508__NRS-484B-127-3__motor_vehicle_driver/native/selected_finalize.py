"""Saved-only caravan measurement and diagnostic Native-result writer."""

import argparse
import hashlib
import json
from pathlib import Path

from meter import measure

SOURCES = ('authored-context.json', 'native_samples.jsonl', 'native-source-inventory.json',
           'video_frames.jsonl', 'trace.jsonl', 'caravan_history.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
CHANNELS = ('drv.following', 'rel.surface_gap', 'drv.queue_behind',
            'rel.same_direction', 'ru.trailer_or_combination',
            'drv.lane_change_feasible', 'kin.speed')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_caravan_space(attempt, source_hashes):
    observed = measure(attempt)
    return {'minimum_clear_space_m': observed['minimum_clear_space_m'],
            'maximum_potential_entrant_length_m': observed['maximum_potential_entrant_length_m'],
            'minimum_static_length_surplus_m': observed['minimum_static_length_surplus_m'],
            'entrant_transition_observed': observed['entrant_transition_observed'],
            'all_caravan_actors_forward_frames': observed['all_caravan_actors_forward_frames'],
            'authority_unverified': True, 'trailer_coupling_unverified': True,
            'legal_sufficiency_judgment': None, 'source_sha256': source_hashes}


def channel_value(name, measurement, frame):
    if name == 'rel.surface_gap':
        return measurement['minimum_clear_space_m']
    if name == 'drv.lane_change_feasible':
        return {'entrant_transition_observed': measurement['entrant_transition_observed'],
                'entry_without_danger_judgment': 'unresolved'}
    if name == 'ru.trailer_or_combination':
        return {'tractor_and_trailer_proxy_measured': True, 'coupling_verified': False}
    if name == 'rel.same_direction':
        return {'all_caravan_actors_forward_frames': measurement['all_caravan_actors_forward_frames']}
    if name == 'kin.speed':
        return {'requested_group_speed_mps': frame['requested_group_speed_mps']}
    if name == 'drv.queue_behind':
        return {'ordered_bodies_measured': True, 'caravan_membership_verified': False}
    if name == 'drv.following':
        return {'same_lane_consecutive_bodies_measured': True}
    raise ValueError('Unknown caravan recording channel')


def finalize(attempt, output):
    from worker_exchange.native_output import physical_result, write_result

    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use fresh sources')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if case_id not in ('training__C228508__NRS-484B-127-3__motor_vehicle_driver__probe_a',
                       'training__C228508__NRS-484B-127-3__motor_vehicle_driver__probe_b'):
        raise ValueError('Exact caravan case differs')
    if construction['case_id'] != case_id or config['law_id'] != 'NRS-484B-127-3' or config['cell_id'] != 'C228508':
        raise ValueError('Exact caravan construction identity differs')
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    measurement = measure_caravan_space(attempt, source_hashes)
    rows = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    description = construction['recording_description']
    if [row['name'] for row in description['channels']] != list(CHANNELS):
        raise ValueError('Caravan recording channels differ')
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    for name in CHANNELS:
        with (channels / (name + '.jsonl')).open('x') as stream:
            for row in rows:
                stream.write(json.dumps({'time_s': row['time_s'],
                                         'value': channel_value(name, measurement, row)}, allow_nan=False) + '\n')
    gap = min(measurement['minimum_clear_space_m'].values())
    requested = config['gap_target_m']
    matched = abs(gap - requested) <= config['gap_tolerance_m']
    result = {'case_id': case_id, 'measured_values': measurement,
              'target_checks': [{'target': 'minimum consecutive clear space',
                  'requested': requested, 'measured': gap,
                  'method': 'original four-corner Native body extent meter',
                  'tolerance': config['gap_tolerance_m'], 'matched': matched,
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['native_samples.jsonl', 'native-source-inventory.json']}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'Saved sources measured; legal review pending',
              'physical_failure_flags': ['Original Native and legal authority need independent review'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description,
              'recording_evidence': [{'name': row['name'], 'unit': row['unit'],
                                      'reference': 'channels/' + row['name'] + '.jsonl'}
                                     for row in description['channels']],
              'realized_observables': {},
              'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {'caravan_space_measurement': {
                  'method': 'measure_caravan_space', 'value': measurement,
                  'sources': source_hashes}},
              'physical_checks': result['physical_checks'],
              'physical_or_legal_acceptance': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
