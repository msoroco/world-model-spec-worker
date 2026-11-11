"""Source-bound diagnostic U-turn finalization; no legal or physical verdict."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return path


def rows(path):
    return [json.loads(line) for line in require(path).read_text().splitlines() if line.strip()]


def measure_turn_crossing(saved):
    return saved.get('centerline_crossing_x_m', saved.get('crossing_x_m'))


def measure_exception_location(saved):
    return saved.get('authored_at_intersection', saved.get('crossing_in_authored_opening'))


def measure_divided_opening(saved):
    return saved['crossing_in_authored_opening']


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    for name in ('construction.json', 'config.json', 'raw.json', 'trace.jsonl', 'video_frames.jsonl'):
        require(attempt/name)
    config = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    if config['case_id'] != construction['case_id'] or config['selected_case_id'] != config['case_id']:
        raise ValueError('Exact case identity differs')
    source = json.loads((attempt/'raw.json').read_text())
    if source.get('case_id') != config['case_id'] or source.get('candidate_id') != config['candidate_id']:
        raise ValueError('Raw source identity differs')
    native = source['rows']
    mapping, trace = rows(attempt/'video_frames.jsonl'), rows(attempt/'trace.jsonl')
    if len(native) != 800 or len(mapping) != 800 or len(trace) != 800:
        raise ValueError('Source/trace/video frame counts differ')
    for index, (item, frame, point) in enumerate(zip(native, mapping, trace)):
        if (item['frame'] != index or item['video_frame'] != index or frame['video_frame'] != index or
            frame['native_frame'] != point['frame'] or frame['carla_frame'] != point['frame'] or
            abs(item['time_s'] - point['time_s']) > 1e-6 or abs(frame['time_s'] - point['time_s']) > 1e-6):
            raise ValueError('Saved source/trace/video identity join differs')
    sys.path.insert(0, str(attempt/'work'/config['assignment_id']/'native'))
    native_root = attempt/'work'/config['assignment_id']/'native'
    bundle = native_root/('divided-opening' if config['case_suffix'].startswith('divided_') else '')/'drafts'/config['case_suffix']/config['candidate_id']
    if config['case_suffix'].startswith('divided_'):
        from saved_divided import process
    else:
        from saved import process
    saved = process(bundle, attempt/'raw.json')
    methods = [('turn_crossing_x_m', measure_turn_crossing),
               ('authored_exception_location', measure_exception_location)]
    if config['case_suffix'].startswith('divided_'):
        methods = [('authored_divided_opening', measure_divided_opening)]
    measurements = {name: {'method': method.__name__, 'value': method(saved),
                            'sources': {'raw.json': sha(attempt/'raw.json')}}
                    for name, method in methods}
    if any(item['value'] is None for item in measurements.values()):
        raise ValueError('Missing derived U-turn measurement')
    report = {'format': 'c111662-current-saved-diagnostic-v1', 'case_id': config['case_id'],
              'candidate_id': config['candidate_id'], 'measurements': measurements,
              'saved_measurement': saved, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    evidence = []
    channel_dir = attempt/'channels'
    channel_dir.mkdir()
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channel_dir/(name+'.jsonl')
        with path.open('x') as stream:
            for item in native:
                actor = item['ego']
                value = {'ego_pose': {'center_xyz_m': actor['center_xyz_m'], 'heading_rad': actor['heading_rad'], 'body_xyz_m': actor['body_xyz_m']},
                         'ego_speed': actor['speed_mps'],
                         'u_turn_at_intersection_or_opening': bool(measure_exception_location(saved))}[name]
                stream.write(json.dumps({'time_s': item['time_s'], 'value': value}, allow_nan=False)+'\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': 'channels/'+path.name})
    road_name = 'road.xodr'
    for name, source_name, output_name in (
        ('authored_road', road_name, 'road-context.json'),
        ('authored_request', 'requested-tracks.jsonl', 'request-context.json')):
        require(attempt/source_name)
        (attempt/output_name).write_text(json.dumps({name:{'source':source_name,
            'sha256':sha(attempt/source_name)}},indent=2)+'\n')
        evidence.append({'name':name,'unit':'structured','reference':output_name})
    crossing = measure_turn_crossing(saved)
    expected = config['case_suffix'] in ('contrast', 'divided_opening')
    measured = bool(measure_exception_location(saved))
    result = {'case_id': config['case_id'],
              'measured_values': {'crossing_x_m': crossing, 'authored_exception_location': measured},
              'target_checks': [{'target': 'authored exception location at U-turn crossing', 'requested': expected,
                                 'measured': measured, 'method': 'saved body center and authored road geometry',
                                 'tolerance': 'one 50 ms frame', 'matched': expected == measured,
                                 'physical_cause_confirmed': False, 'cause_evidence': ['raw.json']}],
              'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': '800-frame diagnostic window; original capture unverified',
              'physical_failure_flags': ['Original Native U-turn and district designation unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': [name+'.mkv' for name in
                  ('overview','approach','reference_corner','driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'crossing_x_m': {'value': crossing, 'unit': 'm',
                  'method': 'source-bound synthetic body crossing', 'time_window': '40 s diagnostic window',
                  'statistic': 'first centerline crossing', 'reference': 'raw.json'}},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    a = p.parse_args()
    print(json.dumps(finalize(a.attempt, a.output), sort_keys=True))
