"""Source-bound saved-only private-way entry measurement, without a legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('road.xodr', 'private-entry-context.json', 'private-entry-actors.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           *(view + '.mkv' for view in VIEWS))


def require(value, message):
    if not value:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line]


def bounds(points):
    require(isinstance(points, list) and len(points) == 4, 'Original actor body incomplete')
    require(all(isinstance(p, list) and len(p) == 2 and
                all(type(v) in (int, float) and math.isfinite(v) for v in p) for p in points),
            'Original actor body nonfinite')
    return min(p[0] for p in points), max(p[0] for p in points), min(p[1] for p in points), max(p[1] for p in points)


def measure_entry(attempt):
    attempt = Path(attempt)
    for name in ('config.json', 'construction.json', 'private-entry-review.json', *SOURCES):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('selected_case_id')
    require(case == config.get('case_id') == construction.get('case_id'), 'Exact selected case differs')
    review = json.loads((attempt / 'private-entry-review.json').read_text())
    require(review.get('case_id') == case, 'Original source review case differs')
    context = json.loads((attempt / 'private-entry-context.json').read_text())
    require(context.get('case_id') == case and context.get('source_kind') in
            ('original_native_private_way_entry', 'synthetic_cpu_private_way_entry'),
            'Original or declared diagnostic private-way context absent')
    for name in SOURCES:
        if context['source_kind'].startswith('synthetic') and name.endswith('.mkv'):
            continue
        require(review.get('source_sha256', {}).get(name) == digest(attempt / name),
                'Reviewed source hash differs: ' + name)
    body_rows = rows(attempt / 'private-entry-actors.jsonl')
    frame_rows = rows(attempt / 'video_frames.jsonl')
    trace_rows = rows(attempt / 'trace.jsonl')
    require(len(body_rows) == len(frame_rows) == len(trace_rows) == 600,
            'Complete 600-frame original sequence required')
    highway_ids = None
    ego_entry = None
    ego_conflict = None
    highway_conflicts = {}
    highway_braking = {}
    previous_speed = {}
    for index, (body, frame, trace) in enumerate(zip(body_rows, frame_rows, trace_rows)):
        native = body.get('native_frame')
        require(type(native) is int and body.get('video_frame') == frame.get('video_frame') == index and
                frame.get('native_frame') == trace.get('frame') == native and
                abs(body.get('time_s', -1) - index / 20) < 1e-6 and
                abs(frame.get('time_s', -1) - index / 20) < 1e-6 and
                abs(trace.get('time_s', -1) - index / 20) < 1e-6,
                'Original Native/trace/video frame or time join differs')
        require(frame.get('camera_native_frames') == {view: native for view in VIEWS},
                'Four source camera frame joins differ')
        actors = body.get('actors', {})
        require(set(actors) == {'ego', 'approach_1', 'approach_2'},
                'Declared participants missing from original source')
        inventory = body.get('all_vehicle_bodies', {})
        ego_id = str(actors['ego']['actor_id'])
        require(ego_id in inventory and all(str(a['actor_id']) in inventory for a in actors.values()),
                'All-vehicle source inventory omitted participant')
        current_ids = set(inventory) - {ego_id}
        require(current_ids, 'No approaching highway vehicle inventoried')
        if highway_ids is None:
            highway_ids = current_ids
        require(current_ids == highway_ids, 'Highway vehicle inventory changed during entry span')
        ego = bounds(actors['ego']['body_xy_m'])
        require(abs(actors['ego']['center_xy_m'][0] - 2) < 3.5,
                'Ego departed private-way crossing alignment')
        require(abs(trace['position_m'][0] - actors['ego']['center_xy_m'][0]) < .25 and
                abs(trace['position_m'][1] - actors['ego']['center_xy_m'][1]) < .25,
                'Core position differs from original ego body source')
        if ego_entry is None and ego[3] >= -4:
            ego_entry = index
        if ego_conflict is None and ego[3] >= -2:
            ego_conflict = index
        for actor_id in sorted(highway_ids):
            actor = inventory[actor_id]
            box = bounds(actor['body_xy_m'])
            require(box[2] > -4.5 and box[3] < .5,
                    'Inventoried vehicle not on approaching highway lane')
            if actor_id not in highway_conflicts and box[1] >= 2:
                highway_conflicts[actor_id] = index
            speed = actor['speed_mps']
            require(type(speed) in (int, float) and math.isfinite(speed),
                    'Highway speed source invalid')
            if actor_id in previous_speed and previous_speed[actor_id] - speed > 1.5:
                highway_braking.setdefault(actor_id, []).append(index)
            previous_speed[actor_id] = speed
    require(ego_entry is not None and ego_conflict is not None,
            'Original ego did not reach highway entry and conflict')
    require(set(highway_conflicts) == highway_ids,
            'Not every inventoried highway vehicle has a measured conflict approach')
    source_hashes = {name: digest(attempt / name) for name in SOURCES}
    source_hashes['private-entry-review.json'] = digest(attempt / 'private-entry-review.json')
    return {'frame_count': 600, 'rate_hz': 20, 'ego_highway_entry_frame': ego_entry,
            'ego_conflict_frame': ego_conflict,
            'all_approaching_highway_actor_ids': sorted(highway_ids),
            'highway_conflict_frames': highway_conflicts,
            'highway_vehicles_before_ego': sum(frame < ego_conflict for frame in highway_conflicts.values()),
            'highway_vehicle_count': len(highway_ids),
            'highway_speed_drop_frame_candidates': highway_braking,
            'source_sha256': source_hashes,
            'right_of_way_verdict': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / 'result.json').exists(),
            'Fresh saved-only private entry finalization required')
    measured = measure_entry(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config['selected_case_id']
    channels = []
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    original_rows = rows(attempt / 'private-entry-actors.jsonl')
    for spec in config['recording_description']['channels']:
        name = spec['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for row in original_rows:
                stream.write(json.dumps({'time_s': row['time_s'], 'value': {
                    'actors': row['actors'], 'all_vehicle_bodies': row['all_vehicle_bodies'],
                    'source_measurement_only': True}}, allow_nan=False) + '\n')
        channels.append({'name': name, 'unit': spec['unit'], 'reference': 'channels/' + path.name})
    report = {'format': 'worker-analysis-report-v1', 'case_id': case,
              'measurements': {'private_way_entry': {'method': 'measure_entry',
                                                     'value': measured,
                                                     'sources': measured['source_sha256']}},
              'legal_verdict_claimed': False, 'physical_acceptance_claimed': False}
    yield_target = case.endswith('__probe_a')
    matched = measured['highway_vehicles_before_ego'] == (
        measured['highway_vehicle_count'] if yield_target else measured['highway_vehicle_count'] - 1)
    result = {'case_id': case, 'measured_values': measured,
              'target_checks': [{'target': 'all approaching vehicles pass before entry' if yield_target else
                                 'entry between two approaching highway arrivals',
                                 'requested': True, 'measured': matched,
                                 'method': 'Original full-body conflict order and all-vehicle inventory',
                                 'tolerance': 0, 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(measured['source_sha256'])}],
              'setup_confirmed': False, 'behavior_attempted': True,
              'maneuver_completed': False, 'termination_reason': 'full 600-frame source diagnostic',
              'physical_failure_flags': ['Native right-of-way and camera visibility require independent review'],
              'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': construction['recording_description'],
              'recording_evidence': channels + [
                  {'name': 'private_way_and_highway', 'unit': 'source context',
                   'reference': 'private-entry-context.json'}],
              'realized_observables': {},
              'provenance_kind': 'synthetic_local_diagnostic' if
              json.loads((attempt / 'private-entry-context.json').read_text())['source_kind'].startswith('synthetic')
              else 'original_native',
              'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
