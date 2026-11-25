"""Recorded-only bicycle-speed analysis; physical and legal judgment remain separate."""
import argparse
import hashlib
import json
import math
from pathlib import Path

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure_bicycle_speed(source, context):
    speeds = [math.hypot(*row['velocity_xy_mps']) for row in source]
    return {'observed_peak_speed_mps': max(speeds),
            'observed_mean_speed_mps': sum(speeds)/len(speeds),
            'bicycle_blueprint': context['bicycle_blueprint'],
            'legal_prudence_verdict': None}


def measure_stop_approach(source, context):
    return {'stop_sign_governs_route': context['stop_sign_governs_route'],
            'approach_lane_verified': context['approach_lane_verified'],
            'minimum_distance_to_stop_line_m': min(-row['center_xy_m'][0] for row in source),
            'source_frames': len(source),
            'municipal_jurisdiction_review_pending': context['municipal_jurisdiction_review_pending']}


def channel(name, row, context):
    x, y = row['center_xy_m']
    speed = math.hypot(*row['velocity_xy_mps'])
    if name == 'ru.bicycle':
        return {'blueprint': row['blueprint'], 'actor_id': row['actor_id']}
    if name == 'kin.speed':
        return {'mps': speed, 'speed_limit_or_legal_cutoff': None}
    if name == 'kin.position':
        return {'center_xy_m': [x, y]}
    if name == 'drv.time_to_conflict':
        return {'to_stop_line_s': max(0, -x/max(speed, 1e-6)), 'surrogate_only': True}
    if name == 'drv.stopping_distance':
        return {'estimated_m_at_3_mps2': speed*speed/6, 'surrogate_only': True}
    if name == 'ru.pedestrian':
        return {'nearby_actor_count': context.get('pedestrian_count', 0), 'source': 'scene survey'}
    if name == 'env.visibility':
        return {'clear_weather': context.get('clear_weather', True)}
    if name == 'env.wet_road':
        return {'wetness': context.get('wetness', 0)}
    if name == 'st.curvature':
        return {'authored_approach_curvature': 0, 'original_map_review_pending': True}
    if name == 'rel.surface_gap':
        return {'stop_line_distance_m': -x}
    if name == 'dev.stop_sign':
        return {'governs_route': context['stop_sign_governs_route']}
    if name == 'camera_frame_join':
        return {'source_frame': row['native_frame']}
    raise ValueError('Unknown channel: '+name)


def finalize(attempt, output):
    root = Path(attempt).resolve()
    config = json.loads(required(root, 'config.json').read_text())
    names = ['native-bicycle-trace.jsonl', 'context.json', 'video_frames.jsonl',
             'trace.jsonl', 'capture/evidence.jsonl']
    for name in names:
        required(root, name)
    for camera in CAMERAS:
        required(root, camera+'.mkv')
    source = rows(root/names[0]); context = json.loads((root/names[1]).read_text())
    mapping = rows(root/names[2]); trace = rows(root/names[3]); evidence = rows(root/names[4])
    if len(source) != 600 or len(mapping) != 600 or len(trace) != 600 or len(evidence) != 600:
        raise ValueError('Full 600-frame source window required')
    for index, (row, mapped, state, event) in enumerate(zip(source, mapping, trace, evidence)):
        frame = row['native_frame']; time_s = row['time_s']
        if (row['sample_index'] != index or mapped['native_frame'] != frame or
                state['frame'] != frame or event['original_frame'] != frame or
                abs(mapped['time_s']-time_s)>1e-4 or
                any(mapped['camera_native_frames'][camera] != frame for camera in CAMERAS)):
            raise ValueError('Original bicycle/camera/capture frame join failed')
        if row['condition'] != config['condition'] or row['fixed_conditions_id'] != context['fixed_conditions_id']:
            raise ValueError('Bicycle condition/context changed')
    original = context['source_kind'] == 'original_native_actor_readback' and all(
        row['source_kind'] == 'original_native_actor_readback' for row in source)
    if not original and not (context['source_kind'] == 'synthetic_native_mock' and
                             all(row['source_kind'] == 'synthetic_native_mock' for row in source)):
        raise ValueError('Missing bicycle law or Native provenance')
    if context['legal_prudence_verdict'] is not None or any(row['legal_verdict'] is not None for row in source):
        raise ValueError('Legal prudence verdict must remain unresolved')
    recording = []
    channel_dir = root/'channels'
    channel_dir.mkdir(exist_ok=True)
    for item in config['recording_description']['channels']:
        name = item['name']; path = channel_dir/(name+'.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': channel(name, row, context)}, separators=(',', ':'))+'\n' for row in source))
        recording.append({'name': name, 'unit': item['unit'], 'reference': 'channels/'+path.name})
    context_view = channel_dir/'bicycle_stop_approach_context.json'
    context_view.write_text(json.dumps({'bicycle_stop_approach_context': {
        'stop_sign_governs_route': context['stop_sign_governs_route'],
        'approach_lane_verified': context['approach_lane_verified'],
        'municipal_jurisdiction_review_pending': context['municipal_jurisdiction_review_pending'],
        'legal_prudence_verdict': None}})+'\n')
    recording.append({'name': 'bicycle_stop_approach_context', 'unit': 'structured',
                      'reference': 'channels/'+context_view.name})
    speed = measure_bicycle_speed(source, context)
    approach = measure_stop_approach(source, context)
    source_hashes = {name: sha(root/name) for name in names}
    result = {'case_id': config['case_id'], 'measured_values': {'speed': speed, 'approach': approach},
              'target_checks': [{'target': 'bicycle_approach_speed',
                                 'requested': config['requested_speed_mps'],
                                 'measured': speed['observed_peak_speed_mps'],
                                 'method': 'original bicycle velocity magnitude',
                                 'tolerance': 2.0,
                                 'matched': abs(speed['observed_peak_speed_mps']-config['requested_speed_mps']) <= 2,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': names[:3]}],
              'setup_confirmed': original, 'behavior_attempted': original,
              'maneuver_completed': original and approach['minimum_distance_to_stop_line_m'] >= 1,
              'termination_reason': 'full original source window' if original else 'synthetic diagnostic window',
              'physical_failure_flags': ['rider_pixels_and_local_governance_unreviewed'],
              'trace_reference': 'trace.jsonl',
              'video_references': [camera+'.mkv' for camera in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': recording,
              'realized_observables': {'observed_peak_speed_mps': {
                  'value': speed['observed_peak_speed_mps'], 'unit': 'm/s',
                  'method': 'source bicycle velocity magnitude', 'time_window': '30 s / 600 frames',
                  'statistic': 'maximum', 'reference': 'native-bicycle-trace.jsonl'}},
              'provenance_kind': 'native' if original else 'synthetic_cpu',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    if (root/'result.json').exists():
        raise ValueError('Saved processing must not overwrite prior Native result')
    report = {'format': 'c111325-bicycle-speed-saved-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {'bicycle_speed_conditions': {
                  'method': 'measure_bicycle_speed', 'value': speed,
                  'sources': {name: source_hashes[name] for name in names[:2]}},
                  'stop_approach_scope': {'method': 'measure_stop_approach',
                                          'value': approach,
                                          'sources': {name: source_hashes[name] for name in names[:3]}}},
              'original_native_source': original,
              'legal_prudence_verdict': None}
    Path(output).write_text(json.dumps(report, indent=2)+'\n')
    (root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))


if __name__ == '__main__':
    main()
