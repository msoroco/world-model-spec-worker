"""Finalize the original speed trace; retain unknown physical cause and legal status."""
import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


TARGET_TOLERANCE_MPS = .2


def target_matched(maximum_mps, target_mps):
    return abs(maximum_mps - target_mps) <= TARGET_TOLERANCE_MPS


def assess(attempt):
    attempt = Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    case = cfg['case']
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    if not trace or len(trace) != len(evidence) or len(trace) != len(mapping):
        raise ValueError('Original trace/evidence/video inventory differs')
    for i, (point, packet, frame) in enumerate(zip(trace, evidence, mapping)):
        if point['frame'] != packet['original_frame'] or point['frame'] != frame.get('carla_frame') or \
                point['frame'] != frame.get('native_frame') or frame.get('video_frame') != i or \
                abs(point['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Original frame identity/time join differs')
    for channel in case['recording_description']['channels']:
        name = channel['name']
        values = rows(attempt / 'channels' / (name + '.jsonl'))
        if len(values) != len(trace) or any(v.get('value') is None or
            abs(v['time_s'] - point['time_s']) > 1e-6 for v, point in zip(values, trace)):
            raise ValueError('Missing or unmatched original channel: ' + name)
    fixture = (attempt / 'fixture-provenance.json').is_file()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv' % i for i in range(4)]
    mapping_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    decoded = {}
    for i, video in enumerate(videos):
        receipt = audit(attempt / video, len(trace), mapping_sha256=mapping_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if not fixture:
            expected = [1920, 1080] if i == 0 else [1280, 720]
            if receipt['dimensions'] != expected:
                raise ValueError('Original camera dimensions differ')
        decoded[video] = receipt['frames']
    values = [float(row['speed_mps']) for row in trace]
    maximum = max(values)
    first_above = next(({'frame': row['frame'], 'time_s': row['time_s'],
        'speed_mps': row['speed_mps']} for row in trace if row['speed_mps'] > 80 * .44704), None)
    target = case['variable_assignments']['commanded_speed_mps']['value']
    final = trace[-1]
    route_completed = bool(not fixture and final['position']['x'] >= 520 and
                           final['speed_mps'] < 2)
    # The exact 79/80/81 mph probes are only 0.44704 m/s apart.  Keep their
    # target windows disjoint; the legal 80 mph crossing uses the raw maximum.
    matched = target_matched(maximum, target)
    report = {'format': 'absolute-speed-capability-v1', 'case_id': case['case_id'],
              'maximum_original_speed_mps': maximum, 'maximum_original_speed_mph': maximum / .44704,
              'first_original_frame_above_80_mph': first_above,
              'commanded_speed_mps': target, 'target_measured_within_0_2_mps': matched,
              'route_end_and_slowdown_observed': route_completed,
              'source_decode_frames': decoded, 'original_frame_join': True,
              'physical_acceptance': False,
              'follow_up_configuration': {'case_id': case['case_id'],
                  'same_target': True, 'requires_new_attempt': not (matched and route_completed),
                  'controller': {'speed_kp': min(.5, cfg['controller']['speed_kp'] + .05)
                      if not fixture and maximum < target - TARGET_TOLERANCE_MPS else cfg['controller']['speed_kp']},
                  'measurement_basis': 'full original speed trace only; diagnostic subset preserves current gain'},
              'unresolved': ['actual vehicle speed capability on this narrow authored corridor',
                             'native roadway/public-highway setup',
                             'four-camera visibility and complete duration']}
    result = {'case_id': case['case_id'], 'measured_values': {'maximum_speed_mps': maximum,
        'first_above_80_mph': first_above, 'frame_count': len(trace)},
        'target_checks': [{'target': 'commanded_speed_mps', 'requested': target,
            'measured': maximum, 'method': 'maximum original actor velocity norm over full recorded trace',
            'tolerance': TARGET_TOLERANCE_MPS, 'matched': matched, 'physical_cause_confirmed': False,
            'cause_evidence': 'trace.jsonl'}],
        'setup_confirmed': False, 'behavior_attempted': not fixture and any(v > 1 for v in values),
        'maneuver_completed': route_completed,
        'termination_reason': 'diagnostic subset; motion incomplete' if fixture else
                              ('measured endpoint and slowdown' if route_completed else 'incomplete motion'),
        'physical_failure_flags': {'physical_cause_unconfirmed': True,
                                   'camera_legibility_unconfirmed': True},
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': case['recording_description'],
        'recording_evidence': [{'name': channel['name'], 'unit': channel['unit'],
            'reference': 'channels/' + channel['name'] + '.jsonl'}
            for channel in case['recording_description']['channels']],
        'realized_observables': {}}
    return report, result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report, result = assess(args.attempt)
    write_result(args.attempt, result)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
