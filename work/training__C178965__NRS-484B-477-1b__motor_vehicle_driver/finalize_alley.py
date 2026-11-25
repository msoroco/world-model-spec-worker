"""Fail-closed saved-only join and alley-width diagnostic from original files."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from alley_measure import ASSIGNMENT, FRAMES, measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt):
    attempt = Path(attempt)
    source_paths = [required(attempt, name) for name in
                    ('vehicle-poses.jsonl', 'video_frames.jsonl', 'alley-inventory.json',
                     'trace.jsonl')]
    poses = _jsonl(source_paths[0])
    frame_map = _jsonl(source_paths[1])
    trace = _jsonl(source_paths[3])
    inventory = json.loads(source_paths[2].read_text())
    expected = FRAMES if inventory.get('source_kind') == 'native_saved_sample' else 9
    if len(poses) != expected or len(frame_map) != expected or len(trace) != expected:
        raise ValueError(f'{expected} original saved frames required')
    for i, (pose, frame, trace_row) in enumerate(zip(poses, frame_map, trace)):
        if pose.get('video_frame') != i or frame.get('video_frame') != i or pose.get('native_frame') != frame.get('native_frame'):
            raise ValueError('original pose/frame-map identity join failed')
        if abs(pose.get('time_s', -1) - frame.get('time_s', -2)) > .005:
            raise ValueError('original pose/frame-map timing join failed')
        if trace_row.get('frame') != pose['native_frame'] or abs(trace_row.get('time_s', -1) - pose['time_s']) > .005:
            raise ValueError('original trace/pose identity join failed')
        position = trace_row.get('position_m')
        if not isinstance(position, list) or len(position) < 2 or any(
                abs(position[j] - pose['subject']['xy_m'][j]) > .01 for j in (0, 1)):
            raise ValueError('original trace/subject body pose differs')
        if abs(trace_row.get('speed_mps', -1) - pose['subject']['speed_mps']) > .01:
            raise ValueError('original trace/subject speed differs')
        camera_frames = frame.get('camera_native_frames')
        if not isinstance(camera_frames, dict) or set(camera_frames) != set(CAMERAS) or any(camera_frames[name] != pose['native_frame'] for name in CAMERAS):
            raise ValueError('four original camera identities missing or mismatched')
    packet = {'assignment_id': ASSIGNMENT, 'source_kind': inventory.get('source_kind'),
              'subject_id': poses[0]['subject']['vehicle_id'],
              'other_id': poses[0]['other']['vehicle_id'], 'frames': poses}
    packet_bytes = json.dumps(packet, sort_keys=True, separators=(',', ':')).encode()
    diagnostic = measure(packet_bytes, source_paths[2].read_bytes())
    diagnostic['original_source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths}
    diagnostic['camera_frame_map_validated'] = True
    diagnostic['video_pixels_decoded'] = False
    return diagnostic


def alley_width_measurement(attempt):
    attempt = Path(attempt)
    names = ('vehicle-poses.jsonl', 'video_frames.jsonl', 'alley-inventory.json',
             'trace.jsonl')
    diagnostic = finalize(attempt)
    return {'method': 'alley_width_measurement', 'value': diagnostic,
            'sources': {name: sha(required(attempt, name)) for name in names}}


def ordinance_review_context(attempt):
    path = required(attempt, 'alley-inventory.json')
    inventory = json.loads(path.read_text())
    fields = ('local_jurisdiction_source_id', 'local_ordinance_review_source_id',
              'other_alley_scope_review_source_id', 'public_highway_source_id',
              'city_block_source_id', 'rear_access_source_id',
              'abutting_property_source_id', 'non_culdesac_source_id')
    if any(not inventory.get(field) for field in fields):
        raise ValueError('Independent alley and ordinance source IDs missing')
    return {'method': 'ordinance_review_context',
            'value': {'source_ids': {field: inventory[field] for field in fields},
                      'site_match_review': inventory.get('site_match_review', 'unverified'),
                      'ordinance_effect': inventory.get('ordinance_effect', 'undetermined'),
                      'legal_result': None},
            'sources': {'alley-inventory.json': sha(path)}}


def derive_channels(attempt, config):
    attempt = Path(attempt)
    poses = _jsonl(required(attempt, 'vehicle-poses.jsonl'))
    mapping = _jsonl(required(attempt, 'video_frames.jsonl'))
    inventory = json.loads(required(attempt, 'alley-inventory.json').read_text())
    names = {item['name'] for item in config['recording_description']['channels']}
    expected = {'subject_and_other_vehicle_poses', 'alley_lateral_boundaries',
                'st.alley', 'drv.standing_or_parked', 'st.lane_width',
                'kin.extent', 'rel.surface_gap', 'rel.occupies'}
    if names != expected or len(poses) != len(mapping):
        raise ValueError('Declared alley channels or original joins differ')
    channels = {name: [] for name in expected}
    for pose, frame in zip(poses, mapping):
        if pose['native_frame'] != frame['native_frame'] or abs(pose['time_s'] - frame['time_s']) > 1e-4:
            raise ValueError('Original alley channel frame/time join differs')
        channels['subject_and_other_vehicle_poses'].append(
            {'time_s': frame['time_s'], 'value': {'subject': pose['subject'], 'other': pose['other']}})
        channels['alley_lateral_boundaries'].append(
            {'time_s': frame['time_s'], 'value': {'edges_m': inventory['alley_lateral_edges_m'],
                                                'source_sha256': sha(attempt / 'alley-inventory.json')}})
        subject, other = pose['subject'], pose['other']
        edges = inventory['alley_lateral_edges_m']
        derived = {
            'st.alley': {'boundary_source_id': inventory['boundary_measurement_source_id'],
                         'site_match_review': inventory.get('site_match_review', 'unverified')},
            'drv.standing_or_parked': {'subject_speed_mps': subject['speed_mps'],
                                      'halt_proxy': subject['speed_mps'] <= .1,
                                      'purpose_source_id': inventory['halt_purpose_review_source_id']},
            'st.lane_width': {'width_m': edges[1] - edges[0], 'edges_m': edges},
            'kin.extent': {'subject_half_width_m': subject['half_width_m'],
                           'other_half_width_m': other['half_width_m']},
            'rel.surface_gap': {'subject_y_m': subject['xy_m'][1],
                                'other_y_m': other['xy_m'][1]},
            'rel.occupies': {'subject_xy_m': subject['xy_m'],
                             'subject_yaw_rad': subject['yaw_rad']}}
        for name, value in derived.items():
            channels[name].append({'time_s': frame['time_s'], 'value': value})
    directory = attempt / 'channels'
    directory.mkdir(exist_ok=True)
    for name, rows in channels.items():
        (directory / (name + '.jsonl')).write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
    (attempt / 'alley-context.json').write_text(json.dumps({
        'independent_alley_review': {'source_sha256': sha(attempt / 'alley-inventory.json'),
                                     'source_kind': inventory['source_kind'],
                                     'site_match_review': inventory.get('site_match_review', 'unverified'),
                                     'ordinance_effect': inventory.get('ordinance_effect', 'undetermined')}},
        indent=2) + '\n')


def measured_parking_completion(attempt, native):
    """Engineering event criterion from original pose/time joins, not a legal label."""
    if not native:
        return False, {}, 'diagnostic fixture cannot prove original Native parking'
    rows = _jsonl(required(attempt, 'vehicle-poses.jsonl'))
    if len(rows) != FRAMES:
        return False, {}, 'original full-duration Native poses missing'
    stationary = [i for i, row in enumerate(rows)
                  if row['subject']['speed_mps'] <= .1]
    runs = []
    for i in stationary:
        if not runs or i != runs[-1][-1] + 1:
            runs.append([i])
        else:
            runs[-1].append(i)
    longest = max(runs, key=len, default=[])
    if not longest:
        return False, {}, 'no measured stationary interval'
    approach = rows[:longest[0]]
    moved = any(row['subject']['speed_mps'] >= 1 for row in approach)
    if approach:
        a = approach[0]['subject']['xy_m']
        b = rows[longest[0]]['subject']['xy_m']
        moved = moved and math.dist(a, b) >= 1.0
    stable = max(math.dist(rows[i]['subject']['xy_m'], rows[longest[0]]['subject']['xy_m'])
                 for i in longest) <= .5
    completed = moved and stable and len(longest) >= 40
    measured = {'halt_duration_s': {'value': len(longest) / 20, 'unit': 's',
                                     'method': 'original 20 Hz Native pose speed and body stability',
                                     'time_window': 'full 600-frame capture', 'statistic': 'longest stationary run',
                                     'reference': 'vehicle-poses.jsonl'},
                'approach_displacement_m': {'value': math.dist(approach[0]['subject']['xy_m'],
                                                                rows[longest[0]]['subject']['xy_m']) if approach else 0,
                                            'unit': 'm', 'method': 'original Native subject pose displacement',
                                            'time_window': 'approach before longest stationary run',
                                            'statistic': 'endpoint distance',
                                            'reference': 'vehicle-poses.jsonl'}}
    return completed, measured, 'original Native approach, stable body and at least 2 s stationary engineering criterion'


def finalize_package(attempt, output):
    from worker_exchange.native_output import provenance_record, write_result
    attempt, output = Path(attempt), Path(output)
    config = json.loads(required(attempt, 'config.json').read_text())
    measurement = alley_width_measurement(attempt)
    value = measurement['value']
    target_m = {'controlled_1': 3.9, 'controlled_at_10': 3.048,
                'controlled_2': 2.4}[config['alley_case']]
    observed = value['minimum_measured_halt_free_width_m']
    if observed is None or not math.isfinite(observed):
        raise ValueError('No original halted cross-section width measurement')
    matched = abs(observed - target_m) <= .3
    derive_channels(attempt, config)
    report = {'format': 'worker-analysis-report-v1', 'case_id': config['case_id'],
              'measurements': {'source_bound_alley_width': measurement,
                               'ordinance_review_context': ordinance_review_context(attempt)},
              'scope': 'Original saved footprint and independently reviewed alley context; no legal conclusion'}
    sources = measurement['sources']
    interval = [{'first_frame': 0, 'last_frame': value['frame_count'] - 1}]
    provenance = provenance_record(attempt)
    native = value['source_kind'] == 'native_saved_sample' and provenance['provenance_kind'] == 'native'
    complete = native and value['frame_count'] == FRAMES
    parked, realized, park_method = measured_parking_completion(attempt, complete)
    checks = {'setup': {'status': 'met' if complete else 'unverified',
                        'method': 'original full-duration source and independent alley-context review',
                        'sources': sources, 'intervals': interval},
              'target': {'status': 'met' if matched else 'not_met',
                         'method': 'source-bound cross-section free-width measurement',
                         'sources': sources, 'intervals': interval},
              'maneuver': {'status': 'met' if parked else ('not_met' if complete else 'unverified'),
                           'method': park_method,
                           'sources': sources, 'intervals': interval}}
    result = {'case_id': config['case_id'], 'measured_values': value,
              'target_checks': [{'target': 'unobstructed alley width at halted subject',
                                 'requested': target_m, 'measured': observed,
                                 'method': 'original source-bound two-footprint cross-section',
                                 'tolerance': .3, 'matched': matched,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(sources)}],
              'setup_confirmed': complete, 'behavior_attempted': bool(value['subject_halt_proxy_frames']),
              'maneuver_completed': parked,
              'termination_reason': 'Source-bound physical park measured; legal review pending' if parked else
                                    'Source-bound width measured; physical park incomplete or unverified',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': [{'name': name, 'unit': 'source', 'reference': name}
                                     for name in ('vehicle-poses.jsonl', 'alley-inventory.json',
                                                  'video_frames.jsonl', 'trace.jsonl')]
                                    + [{'name': item['name'], 'unit': item['unit'],
                                        'reference': 'channels/' + item['name'] + '.jsonl'}
                                       for item in config['recording_description']['channels']],
              'context_input_evidence': {'independent_alley_review': 'alley-context.json'},
              'realized_observables': realized, 'physical_checks': checks,
              'accepted': False, 'legal_verdict_claimed': False,
              **provenance}
    result['recording_evidence'].append({'name': 'independent_alley_review', 'unit': 'structured',
                                         'reference': 'alley-context.json'})
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    write_result(attempt, result)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    print(json.dumps(finalize_package(args.attempt, args.output) if args.output else finalize(args.attempt),
                     sort_keys=True))
