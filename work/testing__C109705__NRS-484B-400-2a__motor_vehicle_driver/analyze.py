"""Measure original 400(2)(a) approach and preserve unknown physical/legal states."""
import argparse
import hashlib
import json
from pathlib import Path

from worker_exchange.media import audit
from worker_exchange.native_output import write_result


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def assess(attempt):
    attempt = Path(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case = config['case']
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    if not trace or len(trace) != len(evidence) or len(trace) != len(mapping):
        raise ValueError('Original trace/evidence/frame map inventory differs')
    for i, (point, event, frame) in enumerate(zip(trace, evidence, mapping)):
        if point['frame'] != event['original_frame'] or point['frame'] != frame.get('carla_frame') or \
                frame.get('native_frame') != point['frame'] or frame.get('video_frame') != i or \
                abs(point['time_s'] - frame['time_s']) > 1e-6:
            raise ValueError('Original source identity/time join differs')
    channels = attempt / 'channels'
    if not channels.is_dir():
        raise ValueError('Original acquisition channels missing')
    channel_names = [c['name'] for c in case['recording_description']['channels']]
    for name in channel_names:
        path = channels / (name + '.jsonl')
        if not path.is_file():
            raise ValueError('Original acquisition channel missing: ' + name)
        values = rows(path)
        if len(values) != len(trace) or any(v.get('value') is None or
                abs(v['time_s'] - t['time_s']) > 1e-6 for v, t in zip(values, trace)):
            raise ValueError('Original channel frame/time/value join differs: ' + name)
    fixture = (attempt / 'fixture-provenance.json').exists()
    videos = ['raw.mkv'] if fixture else ['view%d.mkv' % i for i in range(4)]
    map_sha = hashlib.sha256((attempt / 'video_frames.jsonl').read_bytes()).hexdigest()
    counts = {}
    for i, video in enumerate(videos):
        source = attempt / video
        if not source.is_file():
            raise ValueError('Original source camera missing: ' + video)
        receipt = audit(source, len(trace), mapping_sha256=map_sha,
                        receipt=attempt / ('source-%d.json' % i))
        if not fixture:
            expected = [1920, 1080] if i == 0 else [1280, 720]
            if receipt['dimensions'] != expected:
                raise ValueError('Original camera dimensions differ')
        counts[video] = receipt['frames']
    lateral = case['variable_assignments']['approach_lateral_m']['value']
    approach = [r for r in trace if r['position']['x'] < -11]
    measured = -sum(r['position']['y'] for r in approach) / len(approach) if approach else abs(trace[0]['position']['y'])
    headings = [r['heading_deg'] for r in trace]
    turn_delta = ((headings[-1] - headings[0] + 180) % 360) - 180
    final = trace[-1]['position']
    route_end = not fixture and final['y'] > 65 and abs(final['x'] - lateral) < 1 and abs(turn_delta - 90) < 15
    native = {
        'case_id': case['case_id'],
        'measured_values': {'approach_lateral_m': measured, 'heading_change_deg': turn_delta,
                            'source_frames': len(trace)},
        'target_checks': [{'target': 'approach_lateral_m', 'requested': lateral,
                           'measured': measured, 'method': 'mean original approach world Y, absolute first Y only for diagnostic subset',
                           'tolerance': .35, 'matched': abs(measured-lateral) <= .35,
                           'physical_cause_confirmed': False, 'cause_evidence': 'trace.jsonl'}],
        'setup_confirmed': False, 'behavior_attempted': not fixture and bool(approach),
        'maneuver_completed': bool(route_end),
        'termination_reason': 'diagnostic subset; turn not performed' if fixture else
                              ('measured northbound endpoint' if route_end else 'incomplete original route'),
        'physical_failure_flags': {'visibility_unverified': True, 'native_map_unverified': True},
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': case['recording_description'],
        'recording_evidence': [{'name': c['name'], 'unit': c['unit'],
                                'reference': 'channels/' + c['name'] + '.jsonl'}
                               for c in case['recording_description']['channels']],
        'realized_observables': {},
    }
    report = {'format': 'pilot-approach-capability-v1', 'case_id': case['case_id'],
              'approach_lateral_m': measured, 'heading_change_deg': turn_delta,
              'route_endpoint_observed': bool(route_end), 'decoded_source_frames': counts,
              'source_join': True, 'physical_acceptance': False,
              'follow_up': {'case_id': case['case_id'], 'preserve_targets': True,
                            'requires_new_attempt': not route_end},
              'unresolved': ['native two-directional junction and public-way assumption',
                             'vehicle body position relative to centerline',
                             'four-camera visibility and duration']}
    return report, native


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report, native = assess(args.attempt)
    write_result(args.attempt, native)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
