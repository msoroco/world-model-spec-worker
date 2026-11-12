"""Saved-only source-bound turn-origin finalizer for the westbound center-lane exact case."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from turn_origin_measurement import measure

CASE = 'heldout__C374648__LVMC-11-12-100-C__motor_vehicle_driver__left_center_west'


def _required(root, name):
    path = Path(root)/name
    if not path.is_file() or not path.stat().st_size:
        raise ValueError('Missing required source: ' + name)
    return path, sha256(path.read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def analyze(attempt, *, write_channels=True):
    root = Path(attempt)
    config = json.loads(_required(root, 'config.json')[0].read_text())
    if (config.get('law_id'), config.get('cell_id'), config.get('actor'),
            config.get('selected_case_id')) != ('LVMC-11-12-100-C', 'C374648',
                                                'motor_vehicle_driver', CASE):
        raise ValueError('Wrong exact center-turn finalizer identity')
    names = ('turn_origin_native.jsonl', 'case_context.json',
             'video_frames.jsonl', 'trace.jsonl')
    sources = {name: _required(root, name) for name in names}
    value = measure(sources[names[0]][0])
    native, mapping, trace = (_rows(sources[name][0]) for name in
                              ('turn_origin_native.jsonl', 'video_frames.jsonl', 'trace.jsonl'))
    context = json.loads(sources['case_context.json'][0].read_text())
    if (len(native) != len(mapping) or len(native) != len(trace)
            or context.get('ego_actor_id') != int(value['ego_id'])
            or context.get('target_start_frame') != native[0]['frame']
            or context.get('requested_maneuver') != 'left turn'
            or context.get('designation_authority_verified') is not False):
        raise ValueError('Original center-turn source/intent binding differs')
    for index, (lane, frame, packet) in enumerate(zip(native, mapping, trace)):
        identity = lane['frame'], lane['time_s']
        if (frame.get('video_frame') != index or
                (frame.get('carla_frame'), frame.get('time_s')) != identity or
                (packet.get('frame'), packet.get('time_s')) != identity):
            raise ValueError('Original center-turn frame/trace identity join differs')
    if write_channels:
        channel = root/'turn_origin_observation.jsonl'
        if channel.exists():
            raise ValueError('Retain prior derived turn-origin channel')
        channel.write_text(''.join(json.dumps({
            'frame': row['frame'], 'time_s': row['time_s'],
            'value': {'lane_id': row['lane_id'], 'road_id': row['road_id'],
                      'is_junction': row['is_junction']}}, allow_nan=False) + '\n'
            for row in native))
    hashes = {name: item[1] for name, item in sources.items()}
    center_use = {'candidate_center_lane_occupied_at_turn_origin':
                  value['origin_matches_center_lane'],
                  'authored_left_turn_intent': context['requested_maneuver'] == 'left turn',
                  'designation_authority_verified': False,
                  'legal_preparation_judgment': None}
    return {'format': 'worker-analysis-report', 'case_id': CASE,
            'measurements': {'turn_origin_observation': {
                'method': 'analyze', 'value': value, 'sources': hashes},
                             'center_lane_use': {'method': 'analyze',
                                                 'value': center_use, 'sources': hashes}},
            'limitations': ['Map markings and authored role do not verify statutory designation; source pixels and physical/legal acceptance require review.'],
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def build_result(attempt, report):
    root = Path(attempt)
    config = json.loads((root/'config.json').read_text())
    value = report['measurements']['turn_origin_observation']['value']
    channel = 'turn_origin_observation.jsonl'
    return {'case_id': CASE,
            'measured_values': {'turn_origin_observation': value,
                                'center_lane_use': report['measurements']['center_lane_use']['value']},
            'target_checks': [{'target': 'left-turn origin in candidate center lane',
                               'requested': 'center lane with observed left deflection',
                               'measured': value['origin_matches_center_lane'],
                               'method': 'original Native lane and heading rows',
                               'tolerance': None, 'matched': False,
                               'physical_cause_confirmed': False,
                               'cause_evidence': 'Designation authority and physical review undecided'}],
            'setup_confirmed': False, 'behavior_attempted': True,
            'maneuver_completed': False,
            'termination_reason': 'Saved original turn-origin measurement complete; physical outcome unverified',
            'physical_failure_flags': {'detection_validated': False},
            'trace_reference': 'trace.jsonl',
            'video_references': ['overview.mkv', 'approach.mkv',
                                 'reference_corner.mkv', 'driver_reference.mkv'],
            'video_frame_map_reference': 'video_frames.jsonl',
            'recording_description': config['case']['recording_description'],
            'recording_evidence': [
                {'name': 'turn_origin_observation', 'unit': 'structured',
                 'reference': channel, 'sha256': _required(root, channel)[1]},
                {'name': 'case_context', 'unit': 'structured',
                 'reference': 'case_context.json',
                 'sha256': _required(root, 'case_context.json')[1]}],
            'realized_observables': {'origin_matches_center_lane': {
                'unit': 'indicator', 'method': 'last nonjunction original lane before entry',
                'time_window': 'original approach and junction', 'statistic': 'origin',
                'reference': channel, 'value': int(value['origin_matches_center_lane']),
                'sample_window_s': [0, (value['frame_count']-1)/20]}},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior center-turn analysis report')
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))
