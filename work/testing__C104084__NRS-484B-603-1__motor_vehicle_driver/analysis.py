"""Saved-only source-bound measurements for one original crest attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_crest_finalizer import finalize


def _source(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(row) for row in path.read_text(encoding='utf-8').splitlines()]


def _write(path, value):
    Path(path).write_text(json.dumps(value, sort_keys=True, allow_nan=False) + '\n', encoding='utf-8')


def measure_limit(capture, finalized):
    packet = json.loads(_source(capture, 'reviewed-limit.json').read_text(encoding='utf-8'))
    return {'prescribed_limit_mps': packet['prescribed_limit_mps'],
            'road_id': packet['road_id'], 'source_kind': packet['source_kind'],
            'source_sha256': _sha(capture / 'reviewed-limit.json')}


def measure_crest(capture, finalized):
    return {'crossing': finalized['crest_crossing'],
            'native_map_sha256': finalized['native_map_sha256']
            if 'native_map_sha256' in finalized else
            json.loads(_source(capture, 'crest-manifest.json').read_text())['native_map_sha256']}


def measure_speed(capture, finalized):
    return dict(finalized['speed_profile_witness'])


def measure_other(capture, finalized):
    motion = json.loads(_source(capture, 'motion.json').read_text(encoding='utf-8'))
    if len(motion) != 900:
        raise ValueError('original other vehicle history incomplete')
    actor_ids = {row['other_actor_id'] for row in motion}
    if len(actor_ids) != 1:
        raise ValueError('original other vehicle identity differs')
    return {'actor_id': next(iter(actor_ids)),
            'first_station_m': motion[0]['other_s_m'],
            'last_station_m': motion[-1]['other_s_m'],
            'minimum_body_clearance_m': min(row['body_clearance_m'] for row in motion),
            'observed_frames': len(motion)}


MEASUREMENTS = {
    'prescribed_limit_measurement': (measure_limit, ['capture/crest-source/reviewed-limit.json', 'capture/crest-source/context.json']),
    'crest_measurement': (measure_crest, ['capture/crest-source/grade.json', 'capture/crest-source/native-map.xodr', 'capture/crest-source/motion.json']),
    'speed_decrease_measurement': (measure_speed, ['capture/crest-source/motion.json', 'capture/crest-source/context.json']),
    'other_vehicle_measurement': (measure_other, ['capture/crest-source/motion.json', 'capture/crest-source/other-route.json']),
}


def analyze(attempt, output):
    attempt = Path(attempt)
    output = Path(output)
    config = json.loads(_source(attempt, 'config.json').read_text(encoding='utf-8'))
    case_id = config['selected_case_id']
    capture = attempt / 'capture/crest-source'
    manifest = json.loads(_source(capture, 'crest-manifest.json').read_text(encoding='utf-8'))
    for _, names in MEASUREMENTS.values():
        for name in names:
            _source(attempt, name)
    for name in ('trace.jsonl', 'video_frames.jsonl', 'capture/evidence.jsonl'):
        _source(attempt, name)
    finalized = finalize(capture, manifest, expected_case=case_id)
    motion = json.loads(_source(capture, 'motion.json').read_text(encoding='utf-8'))
    mapping = _rows(_source(attempt, 'video_frames.jsonl'))
    trace = _rows(_source(attempt, 'trace.jsonl'))
    if len(motion) != len(mapping) or len(trace) != len(mapping) or len(mapping) != 900:
        raise ValueError('original motion, trace and camera coverage differ')
    if any(m['frame_id'] != f['carla_frame'] or t['frame'] != f['carla_frame']
           or m['time_s'] != f['time_s'] or t['time_s'] != f['time_s']
           for m, t, f in zip(motion, trace, mapping)):
        raise ValueError('original Native frame/time join differs')
    measurements = {}
    for key, (method, names) in MEASUREMENTS.items():
        paths = {name: _source(attempt, name) for name in names}
        measurements[key] = {'value': method(capture, finalized),
                             'method': method.__name__,
                             'sources': {name: _sha(path) for name, path in paths.items()}}
    channels = attempt / 'channels'
    channels.mkdir(exist_ok=False)
    evidence = []
    description = config['case']['recording_description']
    views = {
        'native_grade': [row['position']['z'] for row in trace],
        'precrest_speed': [row['ego_speed_mps'] for row in motion],
        'other_vehicle': [row['body_clearance_m'] for row in motion],
        'prescribed_limit': [measurements['prescribed_limit_measurement']['value']['prescribed_limit_mps']] * 900,
        'camera_frame_map': [{'video_frame': row['video_frame'],
                              'carla_frame': row['carla_frame']} for row in mapping],
    }
    for channel in description['channels']:
        name = channel['name']
        path = channels / (name + '.jsonl')
        with path.open('x', encoding='utf-8') as stream:
            for identity, value in zip(mapping, views[name]):
                stream.write(json.dumps({'time_s': identity['time_s'], 'value': value},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    context_name = 'reviewed_original_crest_site'
    context_path = channels / (context_name + '.json')
    _write(context_path, {context_name: {
        'limit_sha256': _sha(capture / 'reviewed-limit.json'),
        'native_map_sha256': _sha(capture / 'native-map.xodr'),
        'capture_ref': manifest['native_capture_ref']}})
    evidence.append({'name': context_name, 'unit': 'structured record',
                     'reference': 'channels/' + context_path.name})
    witness = finalized['speed_profile_witness']
    target = {'target': 'selected_precrest_speed_profile', 'requested': True,
              'measured': True, 'method': 'source-bound full-frame original speed and station witness',
              'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
              'cause_evidence': 'Original timing observed; physical necessity and legal duty remain for review'}
    result = {'case_id': case_id, 'measured_values': measurements,
              'target_checks': [target], 'setup_confirmed': True,
              'behavior_attempted': True, 'maneuver_completed': True,
              'termination_reason': 'original 900-frame hill crest passage and saved profile finalized',
              'physical_failure_flags': {}, 'trace_reference': 'trace.jsonl',
              'video_references': ['overview.mkv', 'approach.mkv',
                                   'reference_corner.mkv', 'driver_reference.mkv'],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'physical_acceptance_claimed': False,
              'legal_acceptance_claimed': False,
              'original_source_manifest_sha256': _sha(capture / 'crest-manifest.json'),
              'speed_profile_witness': witness}
    _write(attempt / 'result.json', result)
    report = {'format': 'worker-analysis-report', 'case_id': case_id,
              'measurements': measurements, 'source_manifest_sha256':
              result['original_source_manifest_sha256'],
              'analysis_complete': True,
              'limitations': ['Physical necessity, lawful entry and due care require independent review; no legal verdict.']}
    _write(output, report)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    analyze(args.attempt, args.output)


if __name__ == '__main__':
    main()
