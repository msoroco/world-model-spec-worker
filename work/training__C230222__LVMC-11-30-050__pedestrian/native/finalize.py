"""Source-bound saved crossing finalizer; no legal or physical acceptance claim."""
import argparse
import json
import math
from pathlib import Path
import subprocess

from route_meter import measure_files, distance


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def read_rows(folder, name):
    return [json.loads(line) for line in required(folder, name).read_text().splitlines() if line.strip()]


def route_geometry(folder):
    folder = Path(folder)
    samples = required(folder, 'route-samples.jsonl')
    context = required(folder, 'route-context.json')
    report_path = folder / 'route-geometry-analysis.json'
    if report_path.exists():
        raise ValueError('Derived route geometry already exists')
    return measure_files(samples, context, report_path)


def report(folder, case_id):
    value = route_geometry(folder)
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'crossing_route_geometry': {
                'method': 'route_geometry', 'value': value,
                'sources': {'route-samples.jsonl': value['source_samples_sha256'],
                            'route-context.json': value['source_context_sha256']}}},
            'scope': 'measured route alternatives; legal and original pixel status unassigned'}


def verify_join(attempt, count):
    samples = read_rows(attempt, 'route-samples.jsonl')
    mapping = read_rows(attempt, 'video_frames.jsonl')
    trace = read_rows(attempt, 'trace.jsonl')
    evidence = read_rows(attempt, 'capture/evidence.jsonl')
    native = read_rows(attempt, 'capture/native/frames.jsonl')
    if any(len(rows) != count for rows in (samples, mapping, trace, evidence, native)):
        raise ValueError('Original crossing source counts differ')
    actor_id = samples[0].get('pedestrian_id')
    if actor_id is None:
        raise ValueError('Original pedestrian actor identity missing')
    prior_frame, prior_time = -1, -math.inf
    for index, (s, m, t, e, n) in enumerate(zip(samples, mapping, trace, evidence, native)):
        frame, time = m.get('native_frame'), m.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or frame <= prior_frame or time <= prior_time:
            raise ValueError('Original crossing frame/time order invalid')
        if m.get('video_frame') != index or m.get('carla_frame') != frame:
            raise ValueError('Original crossing camera frame join differs')
        if any(row.get(key) != frame for row, key in ((s, 'native_frame'), (t, 'frame'),
                                                      (e, 'original_frame'), (n, 'frame'))):
            raise ValueError('Original crossing Native frame join differs')
        if any(abs(float(row[key]) - time) > 1e-4 for row, key in
               ((s, 'time_s'), (t, 'time_s'), (e, 'recording_time_s'))):
            raise ValueError('Original crossing timestamp join differs')
        if s.get('pedestrian_id') != actor_id:
            raise ValueError('Original pedestrian actor identity changed')
        if len(m.get('source_rgb_sha256', {})) != 4 or s.get('original_frame_sha256') != m['source_rgb_sha256'].get('route_profile'):
            raise ValueError('Original crossing source RGB hash join differs')
        if [round(v, 3) for v in s['pedestrian_xy_m']] != [round(v, 3) for v in e['ego']['position_m'][:2]]:
            raise ValueError('Original crossing pedestrian pose differs')
        prior_frame, prior_time = frame, time
    manifest = json.loads(required(attempt, 'capture/manifest.json').read_text())
    if manifest.get('extraction_confirmed') is not True or manifest.get('frames') != count:
        raise ValueError('Original crossing extraction incomplete')
    return {'frames': count, 'pedestrian_actor_id': actor_id,
            'first_frame': mapping[0]['native_frame'], 'last_frame': mapping[-1]['native_frame']}


def video_info(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    p = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                        '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                       text=True, capture_output=True, timeout=120)
    if p.returncode:
        raise ValueError('Original crossing video decode failed: ' + path.name)
    rows = json.loads(p.stdout).get('streams', [])
    if len(rows) != 1 or not str(rows[0].get('nb_read_frames', '')).isdigit():
        raise ValueError('Original crossing video frames missing: ' + path.name)
    return int(rows[0]['nb_read_frames']), int(rows[0]['width']), int(rows[0]['height'])


def rebuild_channels(attempt, config, value):
    samples = read_rows(attempt, 'route-samples.jsonl')
    positions = [row['pedestrian_xy_m'] for row in samples]
    cumulative = 0.0
    channels = {item['name']: [] for item in config['recording_description']['channels']}
    context = json.loads(required(attempt, 'route-context.json').read_text())
    for index, row in enumerate(samples):
        if index:
            cumulative += distance(positions[index - 1], positions[index])
        values = {'kin.position': row['pedestrian_xy_m'], 'kin.path_length': cumulative,
                  'st.road_edge': {'origin': context['origin_curb_xy_m'],
                                   'opposite': context['opposite_curb_xy_m']},
                  'st.crosswalk': {'authored_polygons': context['crosswalk_polygons_xy_m'],
                                   'original_pixel_reviewed': False}}
        for name in channels:
            channels[name].append({'time_s': row['time_s'], 'value': values[name]})
    folder = attempt / 'channels'
    folder.mkdir(exist_ok=True)
    for name, rows in channels.items():
        path = folder / (name + '.jsonl')
        if path.exists():
            raise ValueError('Derived route channel already exists: ' + name)
        path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh original crossing attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    count = config['duration_s'] * config['rate_hz']
    if count != 600:
        raise ValueError('Full 30-second crossing window changed')
    joins = verify_join(attempt, count)
    analysis = report(attempt, config['case_id'])
    value = analysis['measurements']['crossing_route_geometry']['value']
    videos = {}
    for camera in config['cameras']:
        name = camera['name'] + '.mkv'
        info = video_info(attempt / name)
        if info != (count, camera['width'], camera['height']):
            raise ValueError('Original crossing camera frames or dimensions differ: ' + name)
        videos[name] = info
    rebuild_channels(attempt, config, value)
    evidence = [{'name': row['name'], 'unit': row['unit'],
                 'reference': 'channels/' + row['name'] + '.jsonl'}
                for row in config['recording_description']['channels']]
    native = value['source_kind'] == 'native_observation'
    result = {'case_id': config['case_id'],
              'measured_values': {'route_geometry': value, 'legal_verdict': 'not_assigned',
                                  'crosswalk_original_reviewed': False},
              'target_checks': [{'target': 'source-bound complete outside-crosswalk route',
                                 'requested': config['condition'],
                                 'measured': {'right_angle_deviation_deg': value['right_angle_deviation_deg'],
                                              'route_excess_length_m': value['route_excess_length_m']},
                                 'method': 'original pedestrian transforms and curb segments',
                                 'tolerance': None, 'matched': False,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['route-samples.jsonl', 'route-context.json']}],
              'setup_confirmed': False, 'behavior_attempted': native,
              'maneuver_completed': False, 'termination_reason': 'full source interval retained',
              'physical_failure_flags': ['original_crosswalk_and_curb_pixels_unreviewed'],
              'trace_reference': 'trace.jsonl', 'video_references': list(videos),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'route_excess_length_m': {
                  'value': value['route_excess_length_m'], 'unit': 'm',
                  'method': 'full original route versus nearest opposite curb',
                  'time_window': 'full 600-frame interval', 'statistic': 'distance difference',
                  'reference': 'route-samples.jsonl'}},
              'provenance_kind': 'native_source_shape_unverified' if native else 'synthetic_local_diagnostic',
              'accepted': False, 'legal_verdict_claimed': False}
    validate_result(result)
    output.write_text(json.dumps({**analysis, 'original_joins': joins, 'video_frames': videos}, indent=2) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    return analysis


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--case-id')
    a = p.parse_args()
    if (a.attempt / 'config.json').is_file():
        result = finalize(a.attempt, a.output)
    else:
        if not a.case_id:
            raise ValueError('Source-only analysis requires --case-id')
        result = report(a.attempt, a.case_id)
        a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'case_id': result['case_id'], 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
