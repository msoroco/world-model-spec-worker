"""Synthetic source-shaped software compatibility, never original evidence."""

import hashlib
import json
from pathlib import Path

from interference import require


def source(root, name):
    path = Path(root) / name
    require(path.is_file() and not path.is_symlink(),
            'Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def analyze_fixture(attempt):
    root = Path(attempt)
    config = json.loads(source(root, 'config.json').read_text())
    marker = json.loads(source(root, 'diagnostic-source-note.json').read_text())
    require(marker.get('source_kind') == 'synthetic_diagnostic_fixture' and
            marker.get('accepted_original_source') is False,
            'synthetic diagnostic provenance missing')
    rows_path = source(root, 'interaction-rows.json')
    rows = json.loads(rows_path.read_text())
    require(len(rows) == 600, '600 synthetic joined interaction rows required')
    case = config['case']
    for index, row in enumerate(rows):
        require(row.get('frame') == index and
                abs(row.get('time_s', -1) - index / 20) < 1e-8 and
                row.get('bicycle_path') == case['bicycle_path_request'] and
                row.get('motor_response') == case['motor_response_request'],
                'synthetic frame and case control join differs')
        for field in ('motor_speed_mps', 'motor_brake', 'body_gap_m',
                      'bicycle_lane'):
            require(field in row, 'synthetic interaction source missing: ' + field)
    observation = {
        'case_id': case['case_id'], 'frame_count': 600,
        'bicycle_path_request': case['bicycle_path_request'],
        'motor_response_request': case['motor_response_request'],
        'authored_intention_target': case['authored_intention_target'],
        'motor_vehicle_moved': any(row['motor_speed_mps'] > 0.1 for row in rows),
        'maximum_motor_brake': max(row['motor_brake'] for row in rows),
        'minimum_body_gap_m': min(row['body_gap_m'] for row in rows),
        'intent_inferred_from_motion': False,
        'legal_judgment': None}
    require(observation['motor_vehicle_moved'],
            'synthetic motor vehicle never moved')
    sources = {'interaction-rows.json': sha(rows_path),
               'diagnostic-source-note.json': sha(source(
                   root, 'diagnostic-source-note.json'))}
    names = {'motor_vehicle_speed': 'motor_speed_mps',
             'motor_brake': 'motor_brake',
             'bicycle_lane': 'bicycle_lane',
             'body_gap': 'body_gap_m',
             'camera_frame_identity': 'frame'}
    evidence = []
    for channel in case['recording_description']['channels']:
        name = channel['name']
        require(name in names, 'unknown synthetic observation channel')
        dest = root / ('channel-' + name + '.jsonl')
        dest.write_text(''.join(json.dumps({
            'time_s': row['time_s'], 'value': row[names[name]]}) + '\n'
                                for row in rows))
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': dest.name})
    context = json.loads(source(root, 'context-original.json').read_text())
    for context_item in case['recording_description']['context_inputs']:
        require(context.get(context_item['name']) is not None,
                'synthetic context missing: ' + context_item['name'])
        evidence.append({'name': context_item['name'],
                         'unit': context_item['unit'],
                         'reference': 'context-original.json'})
    from worker_exchange.native_output import physical_result, write_result
    native = {'case_id': case['case_id'],
              'measured_values': observation,
              'target_checks': [{
                  'target': 'synthetic bicycle/motor interaction protocol',
                  'requested': case, 'measured': observation,
                  'method': '600 synthetic joined rows',
                  'tolerance': None, 'matched': True,
                  'physical_cause_confirmed': False,
                  'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'synthetic compatibility only',
              'physical_failure_flags': ['original_bicycle_motor_scene_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in
                                   ('overview', 'approach',
                                    'reference_corner', 'driver_reference')],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': case['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {},
              'diagnostic_fixture': True,
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    write_result(root, physical_result(root, native))
    return {'format': 'worker-analysis-report',
            'case_id': case['case_id'],
            'analysis_complete': True,
            'diagnostic_fixture': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'measurements': {'electric_bicycle_motor_interaction': {
                'method': 'measure_case',
                'value': observation, 'sources': sources}},
            'limitations': ['Synthetic fixture tests software only; original movement, intention and legal interference remain open.']}
