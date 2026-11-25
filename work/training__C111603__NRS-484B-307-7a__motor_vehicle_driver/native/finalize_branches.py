"""Measure saved pedestrian and concurrent-indication requests, without a verdict."""
import argparse
import hashlib
import json
from pathlib import Path

PREFIX = 'training__C111603__NRS-484B-307-7a__motor_vehicle_driver__'
BRANCHES = ('pedestrian_clearance', 'pedestrian_overlap',
            'concurrent_absent', 'concurrent_present')
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('turn-history.jsonl', 'arrow-context.json', 'video_frames.jsonl',
           'trace.jsonl', 'capture/evidence.jsonl')


def sha(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def measure(attempt, case, config):
    rows = read_rows(attempt / 'turn-history.jsonl')
    mapping = read_rows(attempt / 'video_frames.jsonl')
    trace = read_rows(attempt / 'trace.jsonl')
    context = json.loads((attempt / 'arrow-context.json').read_text())
    if any(len(group) != 600 for group in (rows, mapping, trace)):
        raise ValueError('Expected 600 saved original frame and time joins')
    source_kind = context.get('source_kind')
    if source_kind not in ('original_native', 'synthetic_cpu_diagnostic'):
        raise ValueError('Undeclared branch source kind')
    values = {'ego_motion': [], 'pedestrian_motion': [],
              'arrow_request': [], 'concurrent_request': []}
    crosswalk_frames = []
    first_ego_entry = None
    for index, (row, video, pose) in enumerate(zip(rows, mapping, trace)):
        if (row.get('frame') != index or pose.get('frame') != index
                or abs(row.get('time_s', -1) - index / 20) > 1e-6
                or abs(video.get('time_s', -1) - index / 20) > 1e-6):
            raise ValueError('Saved branch source frame/time join differs')
        if source_kind == 'original_native':
            if (row.get('source_kind') != 'original_native'
                    or row.get('native_frame') != video.get('native_frame')
                    or row.get('other_traffic_lawful_status') is not None
                    or row.get('pedestrian_lawful_status') is not None
                    or row.get('cautiousness_legal_judgment') is not None):
                raise ValueError('Native branch asserts unreviewed legal source')
            ego = row['ego']['position_m']
            pedestrian = row['pedestrian']['position_m'] if row.get('pedestrian') else None
            arrow = row['requested_arrow_lit']
            concurrent = row['requested_concurrent_straight_indication']
        else:
            if (row.get('original_native_observed') is not False
                    or row['requested_arrow']['governs_ego'] != 'requested_unverified'
                    or row.get('pedestrian_lawful_status') is not None
                    or row.get('other_traffic_lawful_status') is not None
                    or row.get('cautiousness_legal_judgment') is not None):
                raise ValueError('Synthetic branch asserts unreviewed fact')
            ego = row['requested_ego_xy_m']
            pedestrian = row['requested_pedestrian_xy_m']
            arrow = row['requested_arrow']['flashing_yellow_lit']
            concurrent = row['requested_concurrent_straight_indication']
        if concurrent != config['requested_concurrent_straight_indication']:
            raise ValueError('Saved concurrent indication differs from construction')
        values['ego_motion'].append(ego)
        values['pedestrian_motion'].append(pedestrian)
        values['arrow_request'].append(arrow)
        values['concurrent_request'].append(concurrent)
        if pedestrian and -3.5 <= pedestrian[0] <= 3.5 and -5.5 <= pedestrian[1] <= -4.5:
            crosswalk_frames.append(index)
        if first_ego_entry is None and -4 <= ego[0] <= 4 and -4 <= ego[1] <= 4:
            first_ego_entry = index
    if first_ego_entry is None:
        raise ValueError('Ego intersection entry absent from source')
    if case.removeprefix(PREFIX).startswith('pedestrian_') and not crosswalk_frames:
        raise ValueError('Pedestrian crosswalk traversal absent from source')
    metric = {'frames': 600, 'first_ego_entry_frame': first_ego_entry,
              'pedestrian_crosswalk_first_frame': min(crosswalk_frames) if crosswalk_frames else None,
              'pedestrian_crosswalk_last_frame': max(crosswalk_frames) if crosswalk_frames else None,
              'pedestrian_inside_at_ego_entry': first_ego_entry in crosswalk_frames,
              'requested_concurrent_straight_indication': config['requested_concurrent_straight_indication'],
              'arrow_governance_verified': False, 'pedestrian_lawful_status_verified': False,
              'cautiousness_legal_judgment': None, 'legal_verdict_claimed': False,
              'source_kind': source_kind}
    return metric, values


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved attempt')
    for name in (*SOURCES, *[view + '.mkv' for view in VIEWS],
                 'config.json', 'construction.json'):
        sha(attempt / name)
    config = json.loads((attempt / 'config.json').read_text())
    construction = json.loads((attempt / 'construction.json').read_text())
    case = config.get('case_id')
    if case not in tuple(PREFIX + branch for branch in BRANCHES) or construction.get('case_id') != case:
        raise ValueError('Exact selected statutory branch differs')
    metric, values = measure(attempt, case, config)
    mapping = read_rows(attempt / 'video_frames.jsonl')
    description = construction['recording_description']
    channels = attempt / 'channels'
    channels.mkdir()
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('Unknown declared branch channel: ' + name)
        ref = 'channels/' + name + '.jsonl'
        with (attempt / ref).open('x') as stream:
            for frame, value in zip(mapping, values[name]):
                stream.write(json.dumps({'time_s': frame['time_s'], 'value': value}) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': ref})
    report = {'format': 'worker-analysis-report', 'case_id': case,
              'measurements': {'statutory_branch_measurement': {
                  'method': 'measure', 'value': metric,
                  'sources': {name: sha(attempt / name) for name in SOURCES}}},
              'source_complete': True, 'diagnostic_fixture': metric['source_kind'] != 'original_native',
              'physical_or_legal_acceptance': False,
              'limitations': ['Signal governance, lawful pedestrian status and cautiousness remain unreviewed']}
    result = {'case_id': case, 'measured_values': metric,
              'target_checks': [{'target': 'source-joined statutory branch request',
                                 'requested': True, 'measured': True,
                                 'method': '600 saved frames, actor positions and signal requests',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': list(SOURCES)}],
              'setup_confirmed': True, 'behavior_attempted': True,
              'maneuver_completed': True,
              'termination_reason': '600-frame source analysis; legal review pending',
              'physical_failure_flags': [], 'trace_reference': 'trace.jsonl',
              'video_references': [view + '.mkv' for view in VIEWS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'accepted': False,
              'provenance_kind': ('native' if metric['source_kind'] == 'original_native'
                                  else 'synthetic_local_diagnostic'),
              'legal_verdict_claimed': False}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    output.write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
