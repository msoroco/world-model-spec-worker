"""Saved-only source-bound finalizer; no CARLA dependency or legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_feature import measure, read_rows

VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
SOURCES = ('native-feature-source.jsonl', 'road-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')
CHANNELS = ('st.grade', 'st.curvature', 'st.sight_distance',
            'drv.sight_distance_adequate', 'st.centre_line', 'rel.occupies',
            'drv.approaching', 'st.one_way_roadway', 'rel.oncoming')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def value(name, row, road):
    if name == 'st.grade':
        return {'feature_kind': road['feature_kind'], 'grade_profile_source': road.get('grade_profile_source')}
    if name == 'st.curvature':
        return {'feature_kind': road['feature_kind'], 'curvature_source': road.get('curvature_source')}
    if name == 'st.sight_distance':
        return {'clear_m': row['sight_clear_m'], 'censored': row['sight_censored']}
    if name == 'drv.sight_distance_adequate':
        return {'clear_m': row['sight_clear_m'], 'available_forward_road_m': row['available_forward_road_m'],
                'legal_adequacy_judgment': None}
    if name == 'st.centre_line':
        return {'source': road['centerline_source'], 'ego_s_m': row['ego_s_m']}
    if name == 'rel.occupies':
        return {'body_min_signed_m': row['ego_body_min_signed_m'],
                'body_max_signed_m': row['ego_body_max_signed_m']}
    if name == 'drv.approaching':
        return row['ego_s_m'] < road['feature_start_s_m'] and row['ego_forward_mps'] > 0
    if name == 'st.one_way_roadway':
        return {'authored_directionality': road['directionality'],
                'legal_highway_authority_verified': road['legal_highway_authority_verified']}
    if name == 'rel.oncoming':
        return {'other_vehicle_id': row['other_vehicle_id'],
                'route_direction': row['other_vehicle_route_direction']}
    raise ValueError('Unknown exact source channel: ' + name)


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain prior analysis; use a fresh attempt')
    for name in (*SOURCES, *VIDEOS, 'config.json', 'construction.json'):
        if not (attempt / name).is_file():
            raise ValueError('Missing required original source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['case_id']
    if case != construction['case_id'] or config.get('supported_case_ids') != [case]:
        raise ValueError('Exact selected case differs')
    road = json.loads((attempt / 'road-context.json').read_text())
    metric = measure(attempt / 'native-feature-source.jsonl', attempt / 'road-context.json')
    rows = read_rows(attempt / 'native-feature-source.jsonl')
    frame_map = read_rows(attempt / 'video_frames.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    if len(frame_map) != 600 or len(trace) != 600:
        raise ValueError('Original trace/video frame count differs')
    for index, (row, mapping, pose) in enumerate(zip(rows, frame_map, trace)):
        if (mapping.get('video_frame') != index or mapping.get('native_frame') != row['native_frame'] or
                abs(mapping.get('time_s', -1) - row['time_s']) > 1e-6 or
                pose.get('frame') != mapping.get('carla_frame', mapping['native_frame'])):
            raise ValueError('Original Native/video/trace time join differs')
    expected = [c['name'] for c in construction['recording_description']['channels']]
    if expected != list(CHANNELS):
        raise ValueError('Selected measurement channels differ')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row, mapping in zip(rows, frame_map):
                stream.write(json.dumps({'time_s': mapping['time_s'],
                                         'value': value(name, row, road)},
                                        allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + path.name})
    for source in construction['recording_description'].get('context_inputs', []):
        if source['name'] != 'road_geometry_source':
            raise ValueError('Unknown selected context input')
        evidence.append({'name': source['name'], 'unit': source['unit'],
                         'reference': 'road-context.json'})
    diagnostic = road.get('source_kind') == 'synthetic_cpu_diagnostic'
    source_hashes = {name: sha(attempt / name) for name in SOURCES}
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'feature': {'method': 'measure_feature',
                  'value': metric, 'sources': source_hashes}},
              'source_complete': True, 'diagnostic_fixture': diagnostic,
              'physical_or_legal_acceptance': False}
    requested_left = any(p['target_lane_id'] != config['ego_lane_id'] for p in config['control_phases'])
    observed_left = metric['left_of_center_frame_count'] > 0
    result = {'case_id': case, 'measured_values': metric,
              'target_checks': [{'target': 'left-of-center body occupancy in the obstructed feature',
                'requested': requested_left, 'measured': observed_left,
                'method': 'measure_feature', 'tolerance': 0,
                'matched': requested_left == observed_left,
                'physical_cause_confirmed': False, 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': False, 'behavior_attempted': not diagnostic,
              'maneuver_completed': False,
              'termination_reason': '600-frame CPU diagnostic' if diagnostic else '600-frame original Native attempt',
              'physical_failure_flags': ['Original roadway authority, visibility, pixels and legal interpretation pending'],
              'trace_reference': 'trace.jsonl', 'video_references': list(VIDEOS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if diagnostic else 'original_native_attempt',
              'accepted': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    finalize(args.attempt, args.output)
