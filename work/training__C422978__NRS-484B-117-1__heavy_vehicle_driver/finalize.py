"""Rebuild a source-bound CPU diagnostic result from retained heavy-vehicle rows."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'native-capture-report.json', 'video_frames.jsonl',
           'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'approach.mkv',
          'reference_corner.mkv', 'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure_sidewalk_overlap(metric):
    return metric['moving_sidewalk_overlap_frames']


def measure_misdemeanor_context(metric):
    return {'alleged_violation': False, 'criminal_finding': None,
            'source_kind': metric['source_kind']}


def measure_reviewed_scope(metric):
    return {'moving_sidewalk_overlap_frames': metric['moving_sidewalk_overlap_frames'],
            'city_sidewalk_authority_verified': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'trace.jsonl', 'config.json',
                 'construction.json'):
        if not (attempt/name).is_file():
            raise ValueError('Missing required source: '+name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    case_id = config['case_id']
    if (case_id != construction['case_id'] or
            case_id != 'training__C422978__NRS-484B-117-1__heavy_vehicle_driver__reference'):
        raise ValueError('Exact reference case differs')
    metric = measure(attempt)
    observed = read_rows(attempt/'native-observed.jsonl')
    mapping = read_rows(attempt/'video_frames.jsonl')
    trace = read_rows(attempt/'trace.jsonl')
    if len(observed) != len(mapping) or len(trace) != 600:
        raise ValueError('Saved original row count differs')
    for row, map_row, point in zip(observed, mapping, trace):
        if (row['native_frame'] != map_row['native_frame'] or
                point['frame'] != map_row['carla_frame'] or
                abs(point['time_s']-map_row['time_s']) > 1e-6):
            raise ValueError('Saved original Native/trace/video join differs')
    channels = attempt/'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for row, map_row in zip(observed, mapping):
                authored_overlap = (row['speed_mps'] > 0.1 and
                                    max(p[1] for p in row['body_native_xy_m']) > 3.5 and
                                    min(p[1] for p in row['body_native_xy_m']) < 7.5)
                if name == 'subject_pose_body_speed':
                    value = {'center_native_xy_m': row['center_native_xy_m'],
                             'body_native_xy_m': row['body_native_xy_m'],
                             'speed_mps': row['speed_mps']}
                elif name == 'ego_pose':
                    value = {'center_native_xy_m': row['center_native_xy_m'],
                             'body_native_xy_m': row['body_native_xy_m']}
                elif name == 'ego_speed':
                    value = row['speed_mps']
                elif name == 'drive_within_sidewalk_area':
                    value = authored_overlap
                elif name == 'sidewalk_occupancy':
                    value = {'native_frame': row['native_frame'],
                             'lane_id': row['native_lane_id'],
                             'authored_road_overlap': authored_overlap,
                             'city_authority_verified': False}
                else:
                    raise ValueError('Unsupported recording channel: ' + name)
                stream.write(json.dumps({'time_s': map_row['time_s'],
                                         'value': value})+'\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/'+path.name})
    values = [
        ('sidewalk_overlap_frames', measure_sidewalk_overlap, 'number'),
        ('misdemeanor_context', measure_misdemeanor_context, 'object'),
        ('reviewed_scope', measure_reviewed_scope, 'object'),
    ]
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': {key: {'method': fn.__name__, 'value': fn(metric),
                                     'sources': {name: sha(attempt/name)
                                                 for name in SOURCES}}
                               for key, fn, _ in values},
              'source_complete': True, 'diagnostic_fixture': True,
              'physical_or_legal_acceptance': False}
    result = {'case_id': case_id,
              'measured_values': {key: value for key, value in metric.items()
                                  if key not in ('legal_verdict',)},
              'target_checks': [{'target': 'moving sidewalk overlap frames',
                                 'requested': 0,
                                 'measured': metric['moving_sidewalk_overlap_frames'],
                                 'method': 'saved body polygon and speed at 20 Hz',
                                 'tolerance': 0,
                                 'matched': metric['moving_sidewalk_overlap_frames'] == 0,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': '600-frame synthetic CPU diagnostic',
              'physical_failure_flags': ['Original Native and City authority unverified'],
              'trace_reference': 'trace.jsonl',
              'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
