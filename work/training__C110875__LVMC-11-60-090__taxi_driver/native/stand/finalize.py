"""Recorded-only taxi first-street measurement; never assigns a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = ('ru.taxicab', 'st.curb_zone', 'dev.regulatory_sign',
            'dev.governs', 'st.intersection', 'drv.turning',
            'kin.heading', 'kin.path_length')


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def first_turn_measurement(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text())
    text = json.loads(required(root, 'law-text.json').read_text())
    if text.get('text') != config['statutory_text'] or text.get('source') != 'LVMC 11.60.090':
        raise ValueError('Exact taxi law source changed')
    road = required(root, 'road.xodr')
    survey_path = required(root, 'route-survey.json')
    survey = json.loads(survey_path.read_text())
    diagnostic = (root / 'fixture-provenance.json').is_file()
    expected = 'synthetic_diagnostic' if diagnostic else 'independently_reviewed_original'
    if survey.get('review_status') != expected or survey.get('road_sha256') != sha(road):
        raise ValueError('Original road and independent route survey required')
    if not survey.get('reviewer'):
        raise ValueError('Route survey reviewer missing')
    if survey.get('first_intersection_station_m') != 80 or survey.get('later_intersection_station_m') != 130:
        raise ValueError('First/later street ordering differs')
    if survey.get('stand_notice_pixel_source') != 'reference_corner.mkv' or survey.get('stand_notice_pixel_sha256') != sha(required(root, 'reference_corner.mkv')):
        raise ValueError('Posted notice pixel source differs')
    for name in CAMERAS:
        required(root, name + '.mkv')
    poses = rows(required(root, 'actor-poses.jsonl'))
    mapping = rows(required(root, 'video_frames.jsonl'))
    trace = rows(required(root, 'trace.jsonl'))
    if len(poses) != 600 or len(mapping) != 600 or len(trace) != 600:
        raise ValueError('Complete 600-frame original source joins required')
    actor_ids = set()
    points = []
    headings = []
    channels = {name: [] for name in CHANNELS}
    for i, (pose, frame, sample) in enumerate(zip(poses, mapping, trace)):
        if (pose.get('video_frame') != i or pose.get('native_frame') != frame.get('native_frame')
                or sample.get('frame') != frame.get('native_frame')
                or abs(pose.get('time_s', -999) - frame.get('time_s', -999)) > .051
                or abs(sample.get('time_s', -999) - frame.get('time_s', -999)) > .051):
            raise ValueError('Original pose/frame/trace identity differs')
        point = pose.get('subject_xyz_m')
        heading = pose.get('heading_deg')
        if not isinstance(point, list) or len(point) != 3 or not all(type(v) in (int, float) and math.isfinite(v) for v in point):
            raise ValueError('Original subject position missing')
        if type(heading) not in (int, float) or not math.isfinite(heading):
            raise ValueError('Original heading missing')
        if abs(sample['position']['x'] - point[0]) > .01 or abs(sample['position']['y'] - point[1]) > .01:
            raise ValueError('Trace position differs from original actor')
        actor_ids.add(pose.get('subject_id'))
        points.append(point)
        headings.append(heading)
        path_length = sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:]))
        values = {'ru.taxicab': {'native_blueprint': pose.get('subject_blueprint_id'),
                    'license_review': survey.get('taxi_license_review')},
                  'st.curb_zone': {'stand_station_m': 5,
                    'designation_review': survey.get('stand_designation_review')},
                  'dev.regulatory_sign': {'sign_station_m': 10,
                    'notice_review': survey.get('posted_notice_review')},
                  'dev.governs': {'first_intersection_station_m': 80,
                    'source_sha256': sha(survey_path)},
                  'st.intersection': {'first_m': 80, 'later_m': 130,
                    'identity_review': survey.get('street_identity_review')},
                  'drv.turning': {'heading_deg': heading,
                    'first_junction_approach': point[0] >= 76},
                  'kin.heading': heading, 'kin.path_length': path_length}
        for name in CHANNELS:
            channels[name].append({'time_s': frame['time_s'], 'value': values[name]})
    if len(actor_ids) != 1 or None in actor_ids:
        raise ValueError('Taxi actor continuity changed')
    if points[0][0] < 0 or points[0][0] > 8:
        raise ValueError('Taxi did not start near authored stand')
    first_frame = next((i for i, point in enumerate(points) if point[0] >= 79), None)
    if first_frame is None:
        raise ValueError('First intersection never approached')
    observed_right = any(point[0] >= 79 and point[1] < -5 and
                         abs(((heading + 90 + 180) % 360) - 180) < 35
                         for point, heading in zip(points[first_frame:], headings[first_frame:]))
    observed_straight = any(point[0] > 86 and abs(point[1]) < 5
                            for point in points[first_frame:])
    observed = 'right' if observed_right else 'straight' if observed_straight else 'indeterminate'
    return {'value': {'observed_first_turn': observed,
                      'requested_first_turn': config['requested_first_turn'],
                      'first_intersection_approach_frame': first_frame,
                      'sampled_path_m': round(sum(math.dist(a[:2], b[:2]) for a, b in zip(points, points[1:])), 3),
                      'stand_designation_review': survey.get('stand_designation_review'),
                      'posted_notice_review': survey.get('posted_notice_review'),
                      'taxi_license_review': survey.get('taxi_license_review'),
                      'street_identity_review': survey.get('street_identity_review')},
            'sources': {name: sha(required(root, name)) for name in
                ('road.xodr', 'route-survey.json', 'actor-poses.jsonl',
                 'video_frames.jsonl', 'trace.jsonl', 'reference_corner.mkv')},
            'channels': channels}


def finalize(root, output):
    from worker_exchange.native_output import physical_result, provenance_record, write_result
    root, output = Path(root), Path(output)
    if output.exists() or (root / 'result.json').exists():
        raise ValueError('Use a fresh saved-processing stage')
    config = json.loads(required(root, 'config.json').read_text())
    measured = first_turn_measurement(root)
    if set(c['name'] for c in config['recording_description']['channels']) != set(CHANNELS):
        raise ValueError('Source channels differ from declared recording')
    channels_dir = root / 'channels'
    channels_dir.mkdir(exist_ok=True)
    for name, values in measured['channels'].items():
        (channels_dir / (name + '.jsonl')).write_text(''.join(
            json.dumps(value, allow_nan=False) + '\n' for value in values))
    analysis = {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
        'measurements': {'source_bound_first_turn': {
            'method': 'first_turn_measurement', 'value': measured['value'],
            'sources': measured['sources']}},
        'scope': 'original taxi trajectory and sourced first-street context; legal outcome unassessed'}
    evidence = [{'name': name, 'unit': 'source', 'reference': name}
                for name in measured['sources']]
    evidence += [{'name': channel['name'], 'unit': channel['unit'],
                  'reference': channel['source']}
                 for channel in config['recording_description']['channels']]
    target = {'target': 'observed original first-street turn',
              'requested': config['requested_first_turn'],
              'measured': measured['value']['observed_first_turn'],
              'method': 'original Native actor pose and surveyed junction order',
              'tolerance': 0,
              'matched': measured['value']['observed_first_turn'] == config['requested_first_turn'],
              'physical_cause_confirmed': False,
              'cause_evidence': ['actor-poses.jsonl', 'route-survey.json']}
    result = {'case_id': config['case_id'], 'measured_values': measured['value'],
              'target_checks': [target], 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Awaiting original source and authority review',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              **provenance_record(root), 'accepted': False,
              'legal_verdict_claimed': False}
    physical_result(root, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    write_result(root, result)
    return analysis


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
