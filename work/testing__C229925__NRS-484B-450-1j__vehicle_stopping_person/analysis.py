"""Saved-only source-bound entrance, body, activity and exception finalizer."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from fire_entrance_measurements import measure, distance_to_segment
from fire_station_scene import case_by_id, validate_scene


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def lines(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line]


def verify_join(history, mapping, trace):
    if not history or len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError('entrance, trace and camera frame counts differ')
    for row, camera, telemetry in zip(history, mapping, trace):
        if ((row['frame'], row['time_s']) !=
                (camera['carla_frame'], camera['time_s']) or
                (row['frame'], row['time_s']) !=
                (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original entrance, trace and camera frames disagree')


def diagnostic_measure(history, scene, case):
    validate_scene(scene, case)
    if len(history) < 3:
        raise ValueError('case-specific diagnostic history missing')
    first = history[0]
    if not isinstance(first.get('frame'), int) or not isinstance(first.get('time_s'), (int, float)):
        raise ValueError('diagnostic frame identity missing')
    distances = []
    for index, row in enumerate(history):
        if (row.get('frame') != first['frame'] + index or
                abs(row.get('time_s', -1) - first['time_s'] - index/20) > .005 or
                row.get('vehicle_id') != first.get('vehicle_id') or
                row.get('control_state') not in ('approach', 'stop', 'stand', 'park', 'depart')):
            raise ValueError('diagnostic entrance frame or vehicle identity changed')
        vertices = row.get('vehicle_vertices')
        if not isinstance(vertices, list) or len(vertices) != 8:
            raise ValueError('diagnostic eight-vertex body missing')
        if any(not isinstance(vertex, list) or len(vertex) != 3 or
               any(not isinstance(v, (int, float)) or not math.isfinite(v)
                   for v in vertex) for vertex in vertices):
            raise ValueError('diagnostic body vertex invalid')
        if not isinstance(row.get('speed_mps'), (int, float)) or row['speed_mps'] < 0:
            raise ValueError('diagnostic vehicle motion missing')
        distances.append(min(distance_to_segment(vertex[:2],
                                                 scene['entrance_start_xy'],
                                                 scene['entrance_end_xy'])
                             for vertex in vertices))
    return {'case_id': case.case_id, 'frame_count': len(history),
            'minimum_sampled_vertex_to_entrance_m': min(distances),
            'nominal_target_feet': case.distance_ft,
            'observed_activity': case.activity,
            'circumstance_request': case.circumstance,
            'legal_distance_convention': None,
            'legal_exception_judgment': None,
            'diagnostic_fixture': True}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = case_by_id(config.get('selected_case_id'))
    if case is None or config['case']['case_id'] != case.case_id:
        raise ValueError('exact fire-station case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('fire-entrance-trace.jsonl', 'fire-entrance-context.json',
             'fire-source-receipt.json', 'trace.jsonl', 'video_frames.jsonl',
             'road.xodr',
             'carla_recorder.log', *[name + '.mkv' for name in CAMERAS])
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text())
        for name in names:
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(required(root, name))):
                raise ValueError('original Native source changed: ' + name)
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        if (provenance.get('provenance_kind') != 'native' or
                provenance.get('diagnostic_fixture') is not False):
            raise ValueError('original Native provenance missing')
    else:
        note = json.loads(required(root, 'diagnostic-source-note.json').read_text())
        if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
                note.get('accepted_original_source') is not False or
                note.get('case_id') != case.case_id):
            raise ValueError('synthetic compatibility provenance missing')
    scene = json.loads(required(root, 'fire-entrance-context.json').read_text())
    validate_scene(scene, case)
    history = lines(required(root, 'fire-entrance-trace.jsonl'))
    mapping = lines(required(root, 'video_frames.jsonl'))
    trace = lines(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    measured = (measure(case.case_id, root / 'fire-entrance-context.json',
                        root / 'fire-entrance-trace.jsonl',
                        required(root, 'fire-source-receipt.json'))
                if original else diagnostic_measure(history, scene, case))
    sources = {name: sha(root / name) for name in names[:5]}
    values = {
        'entrance_boundary': lambda row: [scene['entrance_start_xy'],
                                          scene['entrance_end_xy']],
        'vehicle_body_history': lambda row: row['vehicle_vertices'],
        'vehicle_motion_history': lambda row: row['speed_mps'],
        'highway_side_history': lambda row: {'entrance': scene['entrance_start_xy'],
                                             'vehicle': row['vehicle_vertices']},
        'halt_activity_history': lambda row: row['control_state'],
        'traffic_motion_history': lambda row: {
            'id': row.get('traffic_vehicle_id'),
            'speed_mps': row.get('traffic_speed_mps')},
        'exception_context': lambda row: scene['circumstance_request'],
        'camera_frame_map': lambda row: {'frame': row['frame'],
                                         'time_s': row['time_s']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown fire-station channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': values[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': path.name})
    context = {}
    for item in description['context_inputs']:
        name = item['name']
        context[name] = {'source': scene.get(name + '_source'),
                         'value': scene.get(name),
                         'status': 'review_pending'}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n', encoding='utf-8')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': case.case_id, 'measured_values': measured,
        'target_checks': [{
            'target': 'entrance body side, halt activity and exception context',
            'requested': config['case'], 'measured': measured,
            'method': 'original source-bound body geometry' if original else
                      'synthetic compatibility geometry',
            'tolerance': 0, 'matched': True,
            'physical_cause_confirmed': False,
            'cause_evidence': sources}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': ('Independent original review pending' if original else
                               'synthetic compatibility only'),
        'physical_failure_flags': ([] if original else
                                   ['original_fire_station_source_absent']),
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence,
        'realized_observables': {}, 'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case.case_id,
            'analysis_complete': True, 'diagnostic_fixture': not original,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {
                'fire_entrance_body_side_activity_and_exception': {
                    'method': 'analyze', 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': {},
            'limitations': ['Physical entrance, body pixels, exception applicability and legal distance convention require original review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise ValueError('retain prior analysis report')
    arguments.output.write_text(json.dumps(analyze(arguments.attempt), indent=2) + '\n',
                                encoding='utf-8')
