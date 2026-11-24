"""Source-bound saved pedestrian crossing finalizer; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure_crossing import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
METER_CAMERAS = ('overview', 'pedestrian_front', 'crosswalk_side', 'overpass_context')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(folder, name):
    return [json.loads(line) for line in required(folder, name).read_text().splitlines() if line.strip()]


def measure_selected_crossing(folder):
    folder = Path(folder)
    context = json.loads(required(folder, 'crossing-context.json').read_text())
    required(folder, 'road.xodr')
    poses = rows(folder, 'actor-poses.jsonl')
    mapping = rows(folder, 'video_frames.jsonl')
    if len(poses) != 600 or len(mapping) != 600:
        raise ValueError('Incomplete original crossing source')
    normalized = []
    for index, (pose, frame) in enumerate(zip(poses, mapping)):
        if pose['native_frame'] != frame['native_frame'] or pose['video_frame'] != index:
            raise ValueError('Original pedestrian/frame identity differs')
        cameras = pose['camera_native_frames']
        if set(cameras) != set(CAMERAS) or any(cameras[name] != frame['native_frame'] for name in CAMERAS):
            raise ValueError('Original four-camera join differs')
        normalized.append(dict(pose, source_cameras={name: index for name in METER_CAMERAS}))
    return {'method': 'measure_selected_crossing',
            'value': measure(context, normalized),
            'sources': {name: sha(required(folder, name)) for name in
                        ('actor-poses.jsonl', 'crossing-context.json', 'road.xodr')}}


def verify_original_joins(folder, count):
    trace = rows(folder, 'trace.jsonl')
    evidence = rows(folder, 'capture/evidence.jsonl')
    mapping = rows(folder, 'video_frames.jsonl')
    poses = rows(folder, 'actor-poses.jsonl')
    native = rows(folder, 'capture/native/frames.jsonl')
    if any(len(source) != count for source in (trace, evidence, mapping, poses, native)):
        raise ValueError('Original pedestrian source counts differ')
    previous = -1
    for i, (t, e, m, p, n) in enumerate(zip(trace, evidence, mapping, poses, native)):
        frame, time = m.get('native_frame'), m.get('time_s')
        if type(frame) is not int or frame <= previous or m.get('video_frame') != i:
            raise ValueError('Original frame mapping invalid')
        if any(item != frame for item in (t.get('frame'), e.get('original_frame'), p.get('native_frame'), n.get('frame'))):
            raise ValueError('Original pedestrian source frame differs')
        if any(abs(float(item) - time) > 1e-4 for item in (t['time_s'], e['recording_time_s'], p['time_s'])):
            raise ValueError('Original pedestrian source time differs')
        if any(abs(float(t['position_m'][axis]) - float(value)) > 1e-3 for axis, value in
               enumerate((p['pedestrian_x_m'], p['pedestrian_y_m']))):
            raise ValueError('Original pedestrian position differs')
        previous = frame
    capture = json.loads(required(folder, 'capture/manifest.json').read_text())
    if capture.get('extraction_confirmed') is not True or capture.get('frames') != count:
        raise ValueError('Original capture extraction incomplete')
    return {'frame_count': count, 'first_native_frame': mapping[0]['native_frame'],
            'last_native_frame': mapping[-1]['native_frame']}


def video_frames(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                            '-show_entries', 'stream=nb_read_frames', '-of',
                            'default=noprint_wrappers=1:nokey=1', str(path)],
                           capture_output=True, text=True, timeout=120)
    if probe.returncode or not probe.stdout.strip().isdigit():
        raise ValueError('Source camera decode failed: ' + path.name)
    return int(probe.stdout.strip())


def derive_channels(folder, description):
    source = rows(folder, 'actor-poses.jsonl')
    mapping = rows(folder, 'video_frames.jsonl')
    context = json.loads(required(folder, 'crossing-context.json').read_text())
    destination = Path(folder) / 'channels'
    if destination.exists():
        raise ValueError('Derived channels already exist')
    destination.mkdir()
    names = {channel['name'] for channel in description['channels']}
    expected = {'ru.subject', 'st.crosswalk', 'st.roadway', 'rel.occupies', 'st.intersection', 'kin.position'}
    if names != expected:
        raise ValueError('Recording channel plan differs')
    for name in names:
        with (destination / (name + '.jsonl')).open('x') as output:
            for pose, frame in zip(source, mapping):
                value = {'ru.subject': {'actor_id': pose['pedestrian_id']},
                         'st.crosswalk': context['crosswalks'],
                         'st.roadway': context['roadway_bounds_m'],
                         'rel.occupies': {'x_m': pose['pedestrian_x_m'], 'y_m': pose['pedestrian_y_m'],
                                         'on_overpass_deck': pose['pedestrian_on_overpass_deck']},
                         'st.intersection': context['intersection_inventory'],
                         'kin.position': [pose['pedestrian_x_m'], pose['pedestrian_y_m'], pose['pedestrian_z_m']]}[name]
                output.write(json.dumps({'time_s': frame['time_s'], 'value': value}, allow_nan=False) + '\n')


def finalize(attempt, output):
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original finalization; use a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if (config['duration_s'], config['rate_hz']) != (30, 20):
        raise ValueError('Exact crossing duration changed')
    joins = verify_original_joins(attempt, 600)
    measured = measure_selected_crossing(attempt)
    counts = {name + '.mkv': video_frames(required(attempt, name + '.mkv')) for name in CAMERAS}
    if any(count != 600 for count in counts.values()):
        raise ValueError('Source camera frame count differs')
    derive_channels(attempt, config['recording_description'])
    value = measured['value']
    requested = config['crossing_case'] == 'crosswalk'
    actual = value['entire_roadway_point_path_within_crosswalk']
    evidence = [{'name': channel['name'], 'unit': channel['unit'],
                 'reference': 'channels/' + channel['name'] + '.jsonl'}
                for channel in config['recording_description']['channels']]
    result = {'case_id': config['case_id'], 'measured_values': value,
              'target_checks': [{'target': 'entire sampled roadway point path within a surveyed crosswalk',
                                 'requested': requested, 'measured': actual,
                                 'method': 'original Native pedestrian points versus sourced crosswalk inventory',
                                 'tolerance': 0, 'matched': actual is requested,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['actor-poses.jsonl', 'crossing-context.json']}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': value['roadway_frames'] > 0,
              'termination_reason': 'full original 30-second source interval retained',
              'physical_failure_flags': ['business_district_and_body_containment_review_pending'],
              'trace_reference': 'trace.jsonl', 'video_references': list(counts),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'roadway_frames_outside_all_crosswalks': {
                  'value': value['roadway_frames_outside_all_crosswalks'], 'unit': 'frames',
                  'method': 'count of original at-grade point-path frames outside inventoried crosswalks',
                  'time_window': '600 original frames', 'statistic': 'count',
                  'reference': 'actor-poses.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic', 'accepted': False,
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result, write_result
    validate_result(result)
    report = {'format': 'c188094-saved-crossing-analysis-v1', 'case_id': config['case_id'],
              'candidate_id': config['candidate_id'],
              'measurements': {'business_district_crossing_path': measured},
              'original_joins': joins, 'source_video_frames': counts,
              'scope': 'saved source positions and crosswalk geometry; no independent legal finding'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    write_result(attempt, result)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
