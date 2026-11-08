"""Saved-only C422978 report and Native result; no legal acceptance decision."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure, rows, source

AID = 'training__C422978__LVMC-11-38-030__motorcycle_or_moped_operator'
VIDEOS = ('overview.mkv', 'front.mkv', 'sidewalk.mkv', 'rear.mkv')
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure_sidewalk_occupancy(attempt):
    return measure(attempt)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        source(attempt, name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case_id = config['case_id']
    if (case_id not in (AID+'__witness_1', AID+'__witness_2') or
            case_id != construction['case_id'] or
            config['candidate_id'] not in ('primary','fallback1','fallback2','fallback3')):
        raise ValueError('Exact sidewalk case/configuration differs')
    measured = measure_sidewalk_occupancy(attempt)
    requested = case_id.endswith('__witness_2')
    observed = measured['moving_sidewalk_overlap_frames'] > 0
    packet = rows(attempt / 'native-observed.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    channels = attempt / 'channels'
    channels.mkdir()
    recording = construction['recording_description']
    evidence = []
    for spec in recording['channels']:
        name = spec['name']
        path = channels / (name + '.jsonl')
        with path.open('x') as stream:
            for row, frame in zip(packet, mapping):
                values = {'motorcycle_body_speed': {
                              'native_center_xy_m': row['center_native_xy_m'],
                              'native_body_xy_m': row['body_native_xy_m'],
                              'speed_mps': row['speed_mps'],
                              'motorcycle_blueprint': row['motorcycle_blueprint']},
                          'sidewalk_lane_readback': {
                              'native_road_id': row['native_road_id'],
                              'native_lane_id': row['native_lane_id']},
                          'camera_frame_join': {'native_frame': frame['native_frame'],
                                                'video_frame': frame['video_frame']}}
                stream.write(json.dumps({'time_s': frame['time_s'],
                                         'value': values[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': spec['unit'],
                         'reference': 'channels/' + path.name})
    report = {'format': 'c422978-sidewalk-analysis-v1', 'case_id': case_id,
              'selected': False, 'draft_only': True,
              'measurements': {'motorcycle_sidewalk_occupancy': {
                  'method': 'measure_sidewalk_occupancy', 'value': measured,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = {'case_id': case_id,
              'measured_values': {key: value for key, value in measured.items()
                                  if key != 'legal_verdict'},
              'target_checks': [{'target': 'moving motorcycle body intersects surveyed sidewalk',
                                 'requested': requested, 'measured': observed,
                                 'method': 'saved Native full-body sidewalk occupancy',
                                 'tolerance': 0, 'matched': requested == observed,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'full 480-frame saved motorcycle diagnostic window',
              'physical_failure_flags': ['Original Native and city-sidewalk qualification require independent review'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': recording, 'recording_evidence': evidence,
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if measured['source_kind']=='synthetic_cpu' else 'original_native',
              'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
