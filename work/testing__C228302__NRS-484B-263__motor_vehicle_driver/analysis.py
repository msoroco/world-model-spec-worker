"""Exact-case synthetic exit analyzer for CPU compatibility; no legal finding."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_exit(rows, config, scene):
    if len(rows) != 900 or scene['case_id'] != config['selected_case_id']:
        raise ValueError('exact 900-frame exit case required')
    case = config['case']
    actor_ids = [f'approaching_{index}' for index in range(case['approaching_count'])]
    entry = []
    stopped = []
    minimum = {actor: float('inf') for actor in actor_ids}
    for index, row in enumerate(rows):
        if row.get('frame') != index or abs(row.get('time_s', -1) - index / 20) > 1e-8:
            raise ValueError('synthetic 20 Hz frame join changed')
        if row.get('case_id') != scene['case_id'] or row.get('policy') != case['policy']:
            raise ValueError('synthetic case or policy changed')
        if row.get('approaching_count') != case['approaching_count'] or row.get('approach_headway_s') != case['approach_headway_s']:
            raise ValueError('synthetic approach design changed')
        if [v.get('actor_id') for v in row.get('approaching_vehicles', [])] != actor_ids:
            raise ValueError('all approaching vehicle identities required')
        for vehicle in row['approaching_vehicles']:
            if not vehicle.get('on_highway') or vehicle.get('range_to_interaction_m', -1) < 0:
                raise ValueError('synthetic highway occupancy or range changed')
            minimum[vehicle['actor_id']] = min(minimum[vehicle['actor_id']], vehicle['range_to_interaction_m'])
        if row.get('inside_exit_interaction'):
            entry.append(index)
        elif row.get('ego_speed_mps', -1) <= 0.05:
            stopped.append(index)
    if not entry or not any(frame < entry[0] for frame in stopped):
        raise ValueError('synthetic wait then exit interaction required')
    return {'frame_count': 900, 'first_entry_frame': entry[0],
            'pre_entry_wait_frames': len([frame for frame in stopped if frame < entry[0]]),
            'approaching_actor_ids': actor_ids,
            'minimum_approach_range_m': minimum,
            'requested_policy': case['policy'],
            'immediate_hazard_judgment': None, 'reasonable_safety_judgment': None,
            'physical_acceptance_claimed': False}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    scene = json.loads(required(root, 'scene.json').read_text())
    marker_path = required(root, 'diagnostic-source-note.json')
    marker = json.loads(marker_path.read_text())
    if marker.get('source_kind') != 'synthetic_diagnostic_fixture' or marker.get('accepted_original_source') is not False:
        raise ValueError('synthetic diagnostic provenance required')
    row_path = required(root, 'exit-rows.json')
    rows = json.loads(row_path.read_text())
    measured = measure_exit(rows, config, scene)
    sources = {'exit-rows.json': sha(row_path), 'diagnostic-source-note.json': sha(marker_path)}
    description = config['case']['recording_description']
    value = {
        'controlled_access_designation': lambda row: {'synthetic_readback': True, 'original_authority': False},
        'exit_path': lambda row: {'inside_interaction': row['inside_exit_interaction'], 'ego_speed_mps': row['ego_speed_mps']},
        'all_approaching_vehicles': lambda row: row['approaching_vehicles'],
        'precedence_duration': lambda row: {'ego_waiting': row['ego_speed_mps'] <= 0.05, 'inside_interaction': row['inside_exit_interaction']},
        'camera_frame_identity': lambda row: {'frame': row['frame']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in value:
            raise ValueError('unknown exit channel')
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': value[name](row)}) + '\n' for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'synthetic controlled-access exit protocol',
                                 'requested': config['case'], 'measured': measured,
                                 'method': '900 source-specific synthetic joined rows',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_road_authority_and_exit_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {'controlled_access_exit': {'method': 'measure_exit',
                                                        'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; original authority, map, motion and legal judgment absent.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
