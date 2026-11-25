"""Analyze retained C230259 sources; no legal or physical acceptance verdict."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from slow_traffic_saved_measure import measure_original

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def slow_traffic_observation(folder):
    names = ('slow-traffic-trace.jsonl', 'video_frames.jsonl',
             'slow-traffic-context.json', 'road.xodr')
    sources = {name: required(folder, name) for name in names}
    value = measure_original(*(sources[name].read_bytes() for name in names))
    return {'method': 'slow_traffic_observation', 'value': value,
            'sources': {name: sha(path) for name, path in sources.items()}}


def analysis_report(folder, contract=None):
    config = json.loads(required(folder, 'config.json').read_text())
    return {'format': 'c230259-source-analysis-v1', 'case_id': config['case_id'],
            'analysis_complete': True, 'legal_verdict_claimed': False,
            'measurements': {'slow_traffic_observation': slow_traffic_observation(folder)},
            'limitations': ['Source-shaped CPU diagnostics do not establish public highway status, '
                            'actual traffic impediment, sufficient paved width, extreme-right '
                            'legal placement or NRS 484B.630 applicability.']}


def decoded_frames(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        capture_output=True, text=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + path.name)
    return int(result.stdout.strip())


def finalize(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('rate_hz') != 20 or config.get('duration_s') != 30:
        raise ValueError('C230259 original recording contract changed')
    report = analysis_report(attempt)
    measurement = report['measurements']['slow_traffic_observation']['value']
    counts = {name: decoded_frames(required(attempt, name)) for name in VIDEOS}
    if set(counts.values()) != {600}:
        raise ValueError('Original four-camera frame count differs')
    provenance = provenance_record(attempt)
    native = provenance['provenance_kind'] == 'native' and not provenance['diagnostic_fixture']
    for item in config['recording_description']['channels']:
        if item['name'] not in ('participant_footprints', 'participant_velocity_and_intent'):
            raise ValueError('Unknown required Native channel: ' + item['name'])
    right_requested = config['extreme_right_requested']
    edge = measurement['closest_right_body_edge_to_paved_edge_m']
    result = {'case_id': config['case_id'], 'measured_values': measurement,
        'target_checks': [{'target': 'slow traffic and rightward body placement on surveyed paved highway',
            'requested': 'rightward' if right_requested else 'lane_center',
            'measured': {'closest_right_body_edge_to_paved_edge_m': edge,
                         'frames_follower_behind': measurement['frames_follower_behind'],
                         'follower_command_below_free_flow_frames':
                             measurement['follower_command_below_free_flow_frames']},
            'method': 'original participant bodies, velocities, lane survey and same-frame cameras',
            'tolerance': 'continuous source values; no legal cutoff',
            'matched': False, 'physical_cause_confirmed': False,
            'cause_evidence': ['slow-traffic-trace.jsonl', 'slow-traffic-context.json',
                               'road.xodr', 'video_frames.jsonl']}],
        'setup_confirmed': native and measurement['one_lane_each_direction_surveyed'],
        'behavior_attempted': native, 'maneuver_completed': False,
        'termination_reason': '600 original Native frames retained',
        'physical_failure_flags': ['public_highway_and_impediment_require_independent_review',
                                   'extreme_right_and_paved_width_require_physical_review'],
        'trace_reference': 'slow-traffic-trace.jsonl', 'video_references': list(VIDEOS),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': [
            {'name': 'participant_footprints', 'unit': 'structured',
             'reference': 'slow-traffic-trace.jsonl'},
            {'name': 'participant_velocity_and_intent', 'unit': 'm/s',
             'reference': 'slow-traffic-trace.jsonl'}],
        'realized_observables': {'right_body_edge_to_paved_edge_m': {
            'value': edge, 'unit': 'm', 'method': 'original body footprint and authored edge',
            'time_window': '600 frames', 'statistic': 'minimum absolute distance',
            'reference': 'slow-traffic-trace.jsonl'}},
        'provenance_kind': provenance['provenance_kind'],
        'diagnostic_fixture': provenance['diagnostic_fixture'],
        'accepted': False, 'legal_verdict_claimed': False}
    write_result(attempt, result)
    report.update(candidate_id=config['candidate_id'], source_video_frames=counts,
                  provenance=provenance)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
