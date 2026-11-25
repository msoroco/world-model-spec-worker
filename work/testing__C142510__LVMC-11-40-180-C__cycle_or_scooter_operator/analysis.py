"""Source-specific synthetic compatibility analyzer; never original evidence."""
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


def measure_overtake(rows, config, scene):
    if len(rows) != 900:
        raise ValueError('900 synthetic joined frames required')
    if scene['case_id'] != config['selected_case_id']:
        raise ValueError('exact diagnostic case changed')
    for index, row in enumerate(rows):
        if row['frame'] != index or abs(row['time_s'] - index / 20) > 1e-8:
            raise ValueError('synthetic 20 Hz frame join differs')
        if row['rider_kind'] != scene['rider_kind']:
            raise ValueError('diagnostic rider kind changed')
    passes = [row for row in rows if row['relative_center_x_m'] > 0]
    if not passes or rows[0]['relative_center_x_m'] >= 0:
        raise ValueError('synthetic rider did not pass pedestrian')
    pass_frame = passes[0]['frame']
    emitted = [row['frame'] for row in rows if row['emitted']]
    expected = config['case']['signal_frame']
    if emitted != ([] if expected is None else [expected]):
        raise ValueError('synthetic audible emitter schedule changed')
    braking = [row['frame'] for row in rows if row['brake_applied'] and row['frame'] < pass_frame]
    response = 'yield_brake' if braking else 'advance'
    if response != config['case']['rider_response']:
        raise ValueError('synthetic rider response changed')
    return {'pass_frame': pass_frame, 'signal_frame': expected,
            'signal_before_pass': expected is not None and expected < pass_frame,
            'rider_response': response, 'rider_kind': scene['rider_kind'],
            'joined_frames': len(rows), 'physical_acceptance_claimed': False}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    scene = json.loads(required(root, 'scene.json').read_text())
    marker_path = required(root, 'diagnostic-source-note.json')
    marker = json.loads(marker_path.read_text())
    if marker.get('source_kind') != 'synthetic_diagnostic_fixture' or marker.get('accepted_original_source') is not False:
        raise ValueError('diagnostic fixture provenance missing')
    row_path = required(root, 'overtake-rows.json')
    measured = measure_overtake(json.loads(row_path.read_text()), config, scene)
    sources = {'overtake-rows.json': sha(row_path), 'diagnostic-source-note.json': sha(marker_path)}
    description = config['case']['recording_description']
    values = {
        'sidewalk_body_history': lambda row: {'relative_center_x_m': row['relative_center_x_m'], 'sidewalk_id': scene['sidewalk_id']},
        'pedestrian_audio': lambda row: {'emitted': row['emitted'], 'diagnostic_only': True},
        'rider_response': lambda row: {'brake_applied': row['brake_applied'], 'speed_mps': row['rider_speed_mps']},
        'camera_frame_identity': lambda row: {'frame': row['frame']},
    }
    rows = json.loads(row_path.read_text())
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown sidewalk channel')
        destination = root / ('channel-' + name + '.jsonl')
        destination.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': values[name](row)}) + '\n' for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': destination.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'synthetic sidewalk rider pass and emitter schedule',
                                 'requested': config['case'], 'measured': measured,
                                 'method': '900 source-specific synthetic joined rows',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False, 'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_connected_sidewalk_and_audio_absent'],
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
            'measurements': {'sidewalk_overtake_signal': {'method': 'measure_overtake',
                                                        'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Synthetic fixture tests software only; no original sidewalk, audio, or legal finding.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
