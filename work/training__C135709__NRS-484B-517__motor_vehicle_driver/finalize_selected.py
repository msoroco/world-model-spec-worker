"""Derive selected stand observations from retained Native and review sources.

This produces a diagnostic Native result. A fixture cannot supply derived channels.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(root, name):
    path = Path(root)/name
    if not path.is_file():
        raise ValueError('Missing required source: '+name)
    return path


def read_rows(root, name):
    return [json.loads(line) for line in require(root, name).read_text().splitlines()
            if line.strip()]


def measure_stand_occupancy(rows):
    """Full-body curb polygon occupancy while sampled speed is at most 0.1 m/s."""
    return sum(row['ego']['speed_mps'] <= .1 and all(
        50 <= point[0] <= 75 and -8.25 <= point[1] <= -3.5
        for point in row['ego']['body_native_xyz_m']) for row in rows)


def measure_sign_visibility(rows):
    return sum(row['stand_sign_visible'] and row['stand_polygon_visible'] for row in rows)


def assess_physical_stand(actors, frames, reviews, cfg, sources):
    """Assess sampled maneuver completion, without deciding stand legality.

    Source rows must be original Native readback at acceptance time. CPU mocks
    exercise the branches separately and cannot establish actual completion.
    """
    required = ('native-raw-actors.jsonl', 'video_frames.jsonl',
                'stand-review.jsonl', 'native-map-readback.json')
    bound = {name: sources[name] for name in required if name in sources}
    method = '240 joined original Native actor/body/speed, map and reviewed camera frames'
    if (len(actors) != 240 or len(frames) != 240 or len(reviews) != 240 or
        any(name not in bound for name in required)):
        return {'status': 'unverified', 'method': method, 'sources': bound,
                'missing_evidence': ['complete original Native actor/frame/review/map join'],
                'details': {}, 'legal_verdict_claimed': False,
                'physical_causation_claimed': False}
    try:
        for i, (actor, frame, review) in enumerate(zip(actors, frames, reviews)):
            if (actor['frame'] != i or frame['video_frame'] != i or
                actor['native_frame'] != frame['native_frame'] or
                actor['native_frame'] != review['native_frame'] or
                actor['source_kind'] != 'original_native' or
                actor['speed_source'] != 'original_native' or
                review['review_provenance'] != 'human_frame_review' or
                abs(actor['time_s']-frame['time_s']) > 1e-5 or
                abs(actor['time_s']-review['time_s']) > 1e-5):
                raise ValueError('Original source identity differs')
    except (KeyError, TypeError, ValueError):
        return {'status': 'unverified', 'method': method, 'sources': bound,
                'missing_evidence': ['joined original Native actor/frame/review rows'],
                'details': {}, 'legal_verdict_claimed': False,
                'physical_causation_claimed': False}
    centers = [row['ego']['center_native_xyz_m'] for row in actors]
    sampled_path = sum(math.dist(a[:2], b[:2]) for a, b in zip(centers, centers[1:]))
    final = actors[-30:]
    stopped = sum(row['ego']['speed_mps'] <= .1 for row in final)
    occupied = measure_stand_occupancy(final)
    visible = measure_sign_visibility(reviews[-30:])
    expected = 30 if cfg['requested_stand_occupancy'] else 0
    met = (sampled_path >= 5 and stopped == 30 and occupied == expected and
           visible >= 20)
    return {'status': 'met' if met else 'not_met', 'method': method,
        'sources': bound, 'missing_evidence': [],
        'details': {'sampled_path_m': sampled_path,
                    'final_30_stopped_frames': stopped,
                    'final_30_occupied_frames': occupied,
                    'expected_final_30_occupied_frames': expected,
                    'final_30_reviewed_visible_frames': visible,
                    'engineering_minimum_path_m': 5,
                    'engineering_minimum_visibility_frames': 20,
                    'not_legal_thresholds': True},
        'legal_verdict_claimed': False, 'physical_causation_claimed': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if (attempt/'result.json').exists() or output.exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    for name in ('construction.json', 'config.json', 'stand-road.xodr',
                 'requested-tracks.jsonl', 'native-map-readback.json',
                 'native-capture-report.json'):
        require(attempt, name)
    cfg = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    map_row = json.loads((attempt/'native-map-readback.json').read_text())
    capture = json.loads((attempt/'native-capture-report.json').read_text())
    if (cfg['case_id'] != construction['case_id'] or
        cfg['selected_case_id'] != cfg['case_id'] or
        cfg['road_sha256'] != sha(attempt/'stand-road.xodr') or
        cfg['tracks_sha256'] != sha(attempt/'requested-tracks.jsonl') or
        map_row['road_sha256'] != cfg['road_sha256'] or
        map_row['authored_sign_text'] != 'TAXICAB STAND' or
        capture['case_id'] != cfg['case_id'] or
        capture['candidate_id'] != cfg['candidate_id'] or
        capture['config_sha256'] != sha(attempt/'config.json') or
        capture['observed_frames'] != 240 or capture['error'] is not None):
        raise ValueError('Selected stand source identity differs')
    actors = read_rows(attempt, 'native-raw-actors.jsonl')
    trace = read_rows(attempt, 'trace.jsonl')
    frames = read_rows(attempt, 'video_frames.jsonl')
    reviews = read_rows(attempt, 'stand-review.jsonl')
    requests = read_rows(attempt, 'requested-tracks.jsonl')
    if not all(len(x) == 240 for x in (actors, trace, frames, reviews, requests)):
        raise ValueError('Selected stand source frame count differs')
    source_kind = actors[0]['source_kind']
    if source_kind not in ('synthetic_cpu', 'original_native'):
        raise ValueError('Unknown Native source kind')
    speed_source = ('synthetic_native_sample' if source_kind == 'synthetic_cpu'
                    else 'original_native')
    previous_frame = None
    for i, (actor, point, frame, review, request) in enumerate(zip(
            actors, trace, frames, reviews, requests)):
        ego = actor['ego']
        native_frame = actor['native_frame']
        t = actor['time_s']
        if (actor['frame'] != i or request['frame'] != i or
            actor['requested_phase'] != request['phase'] or
            actor['observed_road_id'] != 517 or
            actor['observed_lane_id'] not in (-1, -2) or
            actor['source_kind'] != source_kind or
            actor['speed_source'] != speed_source or
            frame['video_frame'] != i or frame['native_frame'] != native_frame or
            frame['carla_frame'] != native_frame or
            point['frame'] != native_frame or
            point['position_m'] != ego['center_native_xyz_m'] or
            point['position'] != dict(zip(('x', 'y', 'z'), ego['center_native_xyz_m'])) or
            point['heading_deg'] != ego['yaw_deg'] or
            point['speed_mps'] != ego['speed_mps'] or
            abs(point['time_s']-t) > 1e-5 or
            abs(frame['time_s']-t) > 1e-5 or
            review['frame'] != i or review['native_frame'] != native_frame or
            abs(review['time_s']-t) > 1e-5 or
            review['source_kind'] != source_kind or
            review['review_provenance'] != ('synthetic_cpu' if source_kind == 'synthetic_cpu'
                                             else 'human_frame_review') or
            len(ego['body_native_xyz_m']) != 8 or
            not all(len(vertex) == 3 and all(math.isfinite(v) for v in vertex)
                    for vertex in ego['body_native_xyz_m']) or
            ego['speed_mps'] < 0 or
            not math.isfinite(ego['speed_mps']) or
            (previous_frame is not None and native_frame != previous_frame+1)):
            raise ValueError('Selected stand Native join differs at frame '+str(i))
        previous_frame = native_frame
    source_hashes = {name: sha(attempt/name) for name in
        ('native-raw-actors.jsonl', 'trace.jsonl', 'video_frames.jsonl',
         'stand-review.jsonl', 'native-map-readback.json')}
    occupied = measure_stand_occupancy(actors)
    visible = measure_sign_visibility(reviews)
    measurements = {
        'sampled_stand_occupancy_frames': {'method': 'measure_stand_occupancy',
            'value': occupied, 'sources': {
                'native-raw-actors.jsonl': source_hashes['native-raw-actors.jsonl']}},
        'reviewed_sign_visibility_frames': {'method': 'measure_sign_visibility',
            'value': visible, 'sources': {'stand-review.jsonl': source_hashes['stand-review.jsonl']}}}
    report = {'format': 'c135709-selected-saved-diagnostic-v1',
        'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
        'measurements': measurements, 'source_kind': source_kind,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    channels = attempt/'channels'
    channels.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channels/(name+'.jsonl')
        with path.open('x') as stream:
            for actor, review in zip(actors, reviews):
                ego = actor['ego']
                value = {
                    'ego_pose': {'center_xyz_m': ego['center_native_xyz_m'],
                                 'heading_deg': ego['yaw_deg'],
                                 'body_xyz_m': ego['body_native_xyz_m']},
                    'ego_speed': ego['speed_mps'],
                    'taxicab_stand_occupancy_by_nontaxicab': bool(
                        ego['speed_mps'] <= .1 and all(
                            50 <= p[0] <= 75 and -8.25 <= p[1] <= -3.5
                            for p in ego['body_native_xyz_m'])),
                    'four_source_views': bool(review['stand_sign_visible'] and
                                              review['stand_polygon_visible'])}[name]
                stream.write(json.dumps({'time_s': actor['time_s'], 'value': value},
                                        allow_nan=False)+'\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/'+path.name})
    context = attempt/'stand-context.json'
    context.write_text(json.dumps({'stand_readback': {
        'source': 'native-map-readback.json',
        'sha256': source_hashes['native-map-readback.json']}}, indent=2)+'\n')
    evidence.append({'name': 'stand_readback', 'unit': 'structured',
                     'reference': context.name})
    requested = cfg['requested_stand_occupancy']
    measured = occupied >= 20
    if source_kind == 'original_native':
        physical = assess_physical_stand(actors, frames, reviews, cfg, source_hashes)
        maneuver_completed = physical['status'] == 'met'
        setup_confirmed = physical['status'] != 'unverified'
        behavior_attempted = physical['details'].get('sampled_path_m', 0) >= 1
        failure_flags = ([] if maneuver_completed else
                         ['Observed original stand maneuver did not meet engineering completion criteria'])
    else:
        physical = {'status': 'unverified',
            'method': 'synthetic diagnostic cannot establish original stand motion',
            'sources': source_hashes,
            'missing_evidence': ['original Native acquisition and human frame review'],
            'legal_verdict_claimed': False, 'physical_causation_claimed': False}
        maneuver_completed = setup_confirmed = behavior_attempted = False
        failure_flags = ['Original stand designation, parking purpose and passenger exception unverified']
    result = {'case_id': cfg['case_id'],
        'measured_values': {'sampled_stand_occupancy_frames': occupied},
        'target_checks': [{'target': 'sampled non-taxicab stationary stand occupancy',
            'requested': requested, 'measured': measured,
            'method': 'retained Native body, speed and frame join',
            'tolerance': 'one 50 ms frame', 'matched': requested == measured,
            'physical_cause_confirmed': False,
            'cause_evidence': ['native-raw-actors.jsonl']}],
        'setup_confirmed': setup_confirmed, 'behavior_attempted': behavior_attempted,
        'maneuver_completed': maneuver_completed,
        'termination_reason': '240-frame diagnostic window; physical and legal review pending',
        'physical_failure_flags': failure_flags,
        'physical_checks': {'maneuver': physical},
        'trace_reference': 'trace.jsonl',
        'video_references': [n+'.mkv' for n in
            ('overview', 'approach', 'reference_corner', 'driver_reference')],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': evidence,
        'realized_observables': {'sampled_stand_occupancy_frames': {
            'value': occupied, 'unit': 'frames',
            'method': 'source-bound Native body and speed join',
            'time_window': '12 s diagnostic window', 'statistic': 'stationary full-body frames',
            'reference': 'native-raw-actors.jsonl'}},
        'provenance_kind': ('synthetic_local_diagnostic' if source_kind == 'synthetic_cpu'
                            else 'original_native_unreviewed'), 'accepted': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
