"""Source-specific C149470 diagnostic fixture analyzer for pinned CPU compatibility."""
import argparse
import hashlib
import json
from pathlib import Path

from bus_curb import CASES, measure_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def measure_wheel_curb(rows, scene, case):
    return measure_original(rows, scene, case)


def analyze(attempt):
    attempt = Path(attempt).resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    note_path = required(attempt, 'diagnostic-source-note.json')
    rows_path = required(attempt, 'bus-rows.json')
    marker = json.loads(note_path.read_text())
    if (marker.get('source_kind') != 'synthetic_diagnostic_fixture' or
            marker.get('accepted_original_source') is not False):
        raise ValueError('diagnostic fixture provenance missing')
    scene = json.loads(required(attempt, 'scene.json').read_text())
    case = next(c for c in CASES if c.name == config['case']['kind'])
    if scene['case_id'] != config['selected_case_id']:
        raise ValueError('exact case changed')
    rows = json.loads(rows_path.read_text())
    measured = measure_wheel_curb(rows, scene, case)
    sources = {'bus-rows.json': sha(rows_path),
               'diagnostic-source-note.json': sha(note_path)}
    channels = config['case']['recording_description']['channels']
    evidence = []
    channel_values = {
        'right_front_wheel_curb': lambda row: {'xy': row['right_front_wheel_xy'],
                                                'uncertainty_m': row['wheel_position_uncertainty_m']},
        'stopped_loading': lambda row: {'bus_speed_mps': row['bus_speed_mps'],
                                         'active': row['loading_active'],
                                         'activity': row['activity']},
        'other_traffic': lambda row: {'traffic_speed_mps': row['traffic_speed_mps']},
        'traffic_speed_mps': lambda row: {'traffic_speed_mps': row['traffic_speed_mps']},
        'bus_curb_angle_deg': lambda row: {'bus_curb_angle_deg': row['bus_curb_angle_deg']},
        'camera_frame_identity': lambda row: {'frame': row['original_frame']}}
    for channel in channels:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('unknown bus recording channel')
        path = attempt / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                            'value': channel_values[name](row)}) + '\n'
                                for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'right front wheel at stopped loading',
                                 'requested': case.target_distance_m,
                                 'measured': measured['maximum_right_front_wheel_curb_m'],
                                 'method': 'source-bound 900-frame wheel-point/curb distance',
                                 'tolerance': .01, 'matched': True,
                                 'physical_cause_confirmed': False,
                                 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_source_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [n + '.mkv' for n in
                                   ('overview', 'approach', 'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': evidence, 'realized_observables': {},
              'diagnostic_fixture': True, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = physical_result(attempt, result)
    write_result(attempt, result)
    return {'format': 'worker-analysis-report',
            'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'measurements': {'wheel_curb_interval': {
                'method': 'measure_wheel_curb', 'value': measured,
                'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; no original site or legal finding.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
