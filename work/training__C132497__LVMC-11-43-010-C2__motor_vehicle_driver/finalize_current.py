"""Finalize retained C132497 actor rows for CPU diagnostics or original review.

Diagnostic rows are never treated as original motion or a legal verdict.
"""
import argparse
import hashlib
import json
import math
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


def measure_roundabout_context(observed):
    roads = {row['observed_road_id'] for row in observed}
    return {'entered': 20 in roads, 'circulated': 21 in roads, 'exited': 22 in roads}


def measure_declared_right_exit(observed):
    return any(row['requested_phase'] == 'exit' and row['requested_road_id'] == 22
               for row in observed)


def measure_right_lane_exit(observed):
    circle = [row for row in observed if row['observed_road_id'] == 21]
    exits = [row for row in observed if row['observed_road_id'] == 22]
    return bool(circle and exits and all(row['observed_lane_id'] == -2 for row in circle))


def assess_original_motion(observed, trace, mapping, cfg, map_readback, capture):
    """Assess the finite authored route from retained Native readback, not law.

    The numeric minima are engineering checks for this 240-frame attempt. A
    successful assessment does not establish lane legality, visibility or cause.
    """
    failures = []
    if map_readback.get('road_sha256') != cfg['road_sha256']:
        failures.append('Native map readback differs from authored road')
    if capture.get('case_id') != cfg['case_id'] or capture.get('candidate_id') != cfg['candidate_id'] or capture.get('error') is not None or capture.get('observed_frames') != 240:
        failures.append('Native capture identity or frame count differs')
    expected_lane = cfg['requested_lane_id']
    roads = [row['observed_road_id'] for row in observed]
    lanes = [row['observed_lane_id'] for row in observed]
    entry = [i for i, road in enumerate(roads) if road == 20]
    circle = [i for i, road in enumerate(roads) if road == 21]
    exits = [i for i, road in enumerate(roads) if road == 22]
    if not (roads[0] == 20 and roads[-1] == 22 and len(entry) >= 5 and
            len(circle) >= 10 and len(exits) >= 5 and
            max(entry) < min(circle) and max(circle) < min(exits) and
            all(road in (20, 21, 22) for road in roads)):
        failures.append('Measured entry, circulation and first right-exit sequence incomplete')
    if circle and exits and not (lanes[circle[-1]] == expected_lane and
                                  lanes[exits[0]] == expected_lane and
                                  all(lanes[i] == expected_lane for i in circle)):
        failures.append('Measured circulating and exit lane differ from exact request')
    path_m = sum(math.dist(a['ego']['center_native_xyz_m'][:2],
                           b['ego']['center_native_xyz_m'][:2])
                 for a, b in zip(observed, observed[1:]))
    if path_m < 5.0 or not any(row['ego']['speed_mps'] > 0.5 for row in observed):
        failures.append('Measured original ego progress below authored engineering minimum')
    for i, (row, point, frame) in enumerate(zip(observed, trace, mapping)):
        ego = row['ego']
        if (point.get('frame') != frame.get('carla_frame') or
            point.get('position_m') != ego['center_native_xyz_m'] or
            abs(point.get('speed_mps', -1) - ego['speed_mps']) > 1e-6 or
            abs(point.get('heading_deg', float('inf')) - ego['yaw_deg']) > 1e-6 or
            point.get('velocity_mps') != ego.get('velocity_native_xyz_mps')):
            failures.append('Measured trace differs from actor readback at frame '+str(i))
            break
    return {'setup_confirmed': not any('map readback' in x or 'capture identity' in x for x in failures),
            'behavior_attempted': path_m >= 5.0 and bool(circle) and
                                  any(row['ego']['speed_mps'] > 0.5 for row in observed),
            'maneuver_completed': not failures,
            'physical_failure_flags': failures,
            'physical_checks': {'method': 'retained original Native actor, trace, frame and map readback',
                'engineering_minimum_path_m': 5.0, 'measured_path_m': path_m,
                'entry_frames': len(entry), 'circulation_frames': len(circle),
                'exit_frames': len(exits), 'observed_exit_lane_id':
                    lanes[exits[0]] if exits else None,
                'legal_verdict_claimed': False, 'physical_causation_claimed': False}}


def merge_physical_assessments(generic, route):
    """Require both sampled progress and the exact ordered right-exit route."""
    checks = generic['physical_checks']
    maneuver = checks['maneuver']
    route_check = route['physical_checks']
    maneuver['method'] += ' and ordered first right-exit lane readback'
    maneuver['sources'].update(route_check['sources'])
    maneuver.setdefault('details', {})['right_exit_route'] = route_check
    if not route['maneuver_completed'] and maneuver['status'] == 'met':
        maneuver['status'] = 'not_met'
    checks.update({key: route_check[key] for key in
                   ('sources', 'measured_path_m', 'circulation_frames',
                    'exit_frames', 'observed_exit_lane_id',
                    'engineering_minimum_path_m', 'legal_verdict_claimed',
                    'physical_causation_claimed')})
    return checks


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt/'result.json').exists() or (attempt/'channels').exists():
        raise ValueError('Retain prior finalization; choose a fresh attempt')
    for name in ('construction.json', 'config.json', 'native-raw-actors.jsonl',
                 'trace.jsonl', 'video_frames.jsonl', 'right-exit-road.xodr',
                 'controller-intention.json'):
        require(attempt/name)
    cfg = json.loads((attempt/'config.json').read_text())
    construction = json.loads((attempt/'construction.json').read_text())
    intention = json.loads((attempt/'controller-intention.json').read_text())
    if (cfg['case_id'] != construction['case_id'] or
        cfg['selected_case_id'] != cfg['case_id'] or
        sha(attempt/'right-exit-road.xodr') != cfg['road_sha256'] or
        sha(attempt/'controller-intention.json') != cfg['controller_intention_sha256']):
        raise ValueError('Current case or source identity differs')
    if (intention.get('case_id') != cfg['case_id'] or
        intention.get('candidate_id') != cfg['candidate_id'] or
        intention.get('source_kind') != 'authored_controller_route_before_motion' or
        intention.get('route_road_ids') != [20,21,22] or
        intention.get('intended_exit_road_id') != 22 or
        intention.get('turn_direction') != 'right' or
        intention.get('actual_exit_observed') is not False):
        raise ValueError('Predeclared right-exit controller intention differs')
    observed = rows(attempt/'native-raw-actors.jsonl')
    trace, mapping = rows(attempt/'trace.jsonl'), rows(attempt/'video_frames.jsonl')
    if len(observed) != 240 or len(trace) != 240 or len(mapping) != 240:
        raise ValueError('Saved actor/trace/video lengths differ')
    source_kind = observed[0].get('source_kind')
    if source_kind not in ('synthetic_native_sample', 'original_native'):
        raise ValueError('Unknown saved actor provenance')
    for i, (row, point, frame) in enumerate(zip(observed, trace, mapping)):
        ego = row['ego']
        if (row['frame'] != i or point['frame'] != frame['carla_frame'] or
            row['native_frame'] != frame['native_frame'] or
            abs(row['time_s']-point['time_s']) > 1e-6 or
            abs(frame['time_s']-point['time_s']) > 1e-6 or
            row['source_kind'] != source_kind or
            row['observed_lane_id'] not in (-2, -1) or
            row['observed_road_id'] not in (20, 21, 22, 23) or
            len(ego['body_native_xyz_m']) != 8 or
            not all(math.isfinite(float(value)) for value in
                    (*ego['center_native_xyz_m'], ego['yaw_deg'], ego['speed_mps']))):
            raise ValueError('Saved actor/trace/video identity differs at frame '+str(i))
    if observed[0]['requested_phase'] != 'entry' or observed[-1]['requested_phase'] != 'exit':
        raise ValueError('Saved right-exit route phases differ')
    methods = (('roundabout_context', measure_roundabout_context),
               ('declared_right_exit', measure_declared_right_exit),
               ('right_lane_exit', measure_right_lane_exit))
    raw_hash = sha(attempt/'native-raw-actors.jsonl')
    measurements = {name: {'method': method.__name__, 'value': method(observed),
                           'sources': {'native-raw-actors.jsonl': raw_hash}}
                    for name, method in methods}
    report = {'format': 'c132497-current-saved-diagnostic-v1',
              'case_id': cfg['case_id'], 'candidate_id': cfg['candidate_id'],
              'measurements': measurements, 'source_kind': source_kind,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    path_length = [0.0]
    for previous, current in zip(observed, observed[1:]):
        a,b = previous['ego']['center_native_xyz_m'], current['ego']['center_native_xyz_m']
        path_length.append(path_length[-1] + math.dist(a[:2], b[:2]))
    channel_dir = attempt/'channels'
    channel_dir.mkdir()
    evidence = []
    for channel in construction['recording_description']['channels']:
        name = channel['name']
        path = channel_dir/(name+'.jsonl')
        with path.open('x') as stream:
            for i,row in enumerate(observed):
                ego = row['ego']
                value = {'ego_pose': {'center_xyz_m': ego['center_native_xyz_m'],
                                      'heading_deg': ego['yaw_deg'],
                                      'body_xyz_m': ego['body_native_xyz_m']},
                         'ego_speed': ego['speed_mps'],
                         'ego_lane_id': row['observed_lane_id'],
                         'ego_road_id': row['observed_road_id'],
                         'path_length_m': path_length[i],
                         'right_lane_exit': bool(row['observed_road_id'] == 21 and
                                                 row['observed_lane_id'] == -2)}[name]
                stream.write(json.dumps({'time_s': row['time_s'], 'value': value},
                                        allow_nan=False)+'\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/'+path.name})
    for name, source, target in (
        ('authored_road', 'right-exit-road.xodr', 'road-context.json'),
        ('predeclared_intention', 'controller-intention.json', 'intention-context.json')):
        (attempt/target).write_text(json.dumps({name: {'source': source,
            'sha256': sha(attempt/source)}}, indent=2)+'\n')
        evidence.append({'name': name, 'unit': 'structured', 'reference': target})
    measured = measurements['right_lane_exit']['value']
    requested = cfg['requested_lane_id'] == -2
    if source_kind == 'original_native':
        map_readback = json.loads(require(attempt/'native-map-readback.json').read_text())
        capture = json.loads(require(attempt/'native-capture-report.json').read_text())
        physical = assess_original_motion(observed, trace, mapping, cfg, map_readback, capture)
        physical['physical_checks']['sources'] = {name: sha(attempt/name) for name in
            ('native-raw-actors.jsonl', 'trace.jsonl', 'video_frames.jsonl',
             'native-map-readback.json', 'native-capture-report.json')}
    else:
        physical = {'setup_confirmed': False, 'behavior_attempted': False,
                    'maneuver_completed': False,
                    'physical_failure_flags': ['Synthetic Native motion cannot establish original physical completion'],
                    'physical_checks': {'method': 'synthetic diagnostic only',
                                        'legal_verdict_claimed': False}}
    result = {'case_id': cfg['case_id'], 'measured_values': {'right_lane_exit': measured},
              'target_checks': [{'target': 'right lane while taking intended right exit',
                                 'requested': requested, 'measured': measured,
                                 'method': 'retained actor road/lane and exit rows',
                                 'tolerance': 'one 50 ms frame', 'matched': requested == measured,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': ['native-raw-actors.jsonl']}],
              'setup_confirmed': physical['setup_confirmed'],
              'behavior_attempted': physical['behavior_attempted'],
              'maneuver_completed': physical['maneuver_completed'],
              'termination_reason': '240-frame diagnostic window; original Native review pending',
              'physical_failure_flags': physical['physical_failure_flags'],
              'physical_checks': physical['physical_checks'],
              'trace_reference': 'trace.jsonl',
              'video_references': [n+'.mkv' for n in
                  ('overview','approach','reference_corner','driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'right_lane_frames': {'value': sum(
                  row['observed_road_id'] == 21 and row['observed_lane_id'] == -2
                  for row in observed), 'unit': 'frames',
                  'method': 'source-bound saved actor road/lane join',
                  'time_window': '12 s diagnostic window', 'statistic': 'circulation right-lane frames',
                  'reference': 'native-raw-actors.jsonl'},
                  'path_length_m': {'value': path_length[-1], 'unit': 'm',
                  'method': 'retained consecutive actor center distances',
                  'time_window': '12 s diagnostic window', 'statistic': 'cumulative path length',
                  'reference': 'native-raw-actors.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic' if source_kind == 'synthetic_native_sample'
                                 else 'original_native_unreviewed', 'accepted': False}
    if source_kind == 'original_native':
        from worker_exchange.native_output import assess_physical
        generic = assess_physical(attempt, cfg, result['target_checks'])
        result['physical_checks'] = merge_physical_assessments(generic, physical)
        result['maneuver_completed'] = (result['physical_checks']['maneuver']['status'] == 'met')
        result['setup_confirmed'] = (generic['setup_confirmed'] and physical['setup_confirmed'])
        result['behavior_attempted'] = (generic['behavior_attempted'] and physical['behavior_attempted'])
    else:
        result['physical_checks']['maneuver'] = {
            'status': 'unverified', 'method': 'synthetic diagnostic cannot establish Native motion',
            'sources': {'native-raw-actors.jsonl': raw_hash},
            'missing_evidence': ['original Native acquisition'],
            'legal_verdict_claimed': False, 'physical_causation_claimed': False}
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
