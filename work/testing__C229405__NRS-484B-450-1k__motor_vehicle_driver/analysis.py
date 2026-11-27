"""Saved-only original or synthetic excavation and passage finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from excavation_park import CASES, available_passage_width, measure_original, separation, validate_scene

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
    if len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError('excavation, trace and camera frame counts differ')
    for row, camera, telemetry in zip(history, mapping, trace):
        if ((row['original_frame'], row['time_s']) !=
                (camera['carla_frame'], camera['time_s']) or
                (row['original_frame'], row['time_s']) !=
                (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original excavation, trace and camera frames disagree')


def diagnostic_measure(history, scene, case):
    """Exercise case geometry without treating short fixtures as Native evidence."""
    validate_scene(scene, case)
    if len(history) < 3:
        raise ValueError('case-specific diagnostic history missing')
    vehicle_ids = {row.get('vehicle_id') for row in history}
    traffic_ids = {row.get('traffic_id') for row in history}
    if len(vehicle_ids) != 1 or len(traffic_ids) != 1 or None in vehicle_ids | traffic_ids:
        raise ValueError('diagnostic participant identity changed')
    for row in history:
        if (row.get('relation') != case.relation or
                row.get('halt_activity') != case.activity or
                row.get('exception') != case.exception or
                row.get('excavation_source_sha256') != scene['excavation_source_sha256']):
            raise ValueError('diagnostic excavation or exception context changed')
        for field in ('frame', 'vehicle_motion', 'vehicle_body', 'excavation',
                      'passage', 'traffic_motion', 'activity', 'exception'):
            if not row.get(field + '_source_sha256'):
                raise ValueError('diagnostic original-source shape missing: ' + field)
        width = available_passage_width(scene['traffic_lane_span_y_m'],
                                        row['vehicle_body_rect_m'],
                                        row['excavation_rect_m'])
        if abs(width - row['passage_width_m']) > .001:
            raise ValueError('diagnostic passage geometry differs from case')
    return {'case_id': case.case_id, 'frame_count': len(history),
            'minimum_body_excavation_gap_m': min(separation(
                row['vehicle_body_rect_m'], row['excavation_rect_m']) for row in history),
            'minimum_available_passage_width_m': min(row['passage_width_m']
                                                     for row in history),
            'maximum_traffic_speed_mps': max(row['traffic_speed_mps']
                                             for row in history),
            'observed_activity': case.activity,
            'exception_context': case.exception,
            'legal_obstruction_judgment': None,
            'legal_exception_judgment': None,
            'diagnostic_fixture': True}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = next((item for item in CASES
                 if config['selected_case_id'].endswith('__' + item.case_id)), None)
    if case is None:
        raise ValueError('exact excavation case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('excavation-history.jsonl', 'excavation-site.json', 'trace.jsonl',
             'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
             *[name + '.mkv' for name in CAMERAS])
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
                note.get('case_id') != config['selected_case_id']):
            raise ValueError('synthetic compatibility provenance missing')
    packet = json.loads(required(root, 'excavation-site.json').read_text())
    scene = packet['scene']
    validate_scene(scene, case)
    history = lines(required(root, 'excavation-history.jsonl'))
    mapping = lines(required(root, 'video_frames.jsonl'))
    trace = lines(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    measured = measure_original(history, scene, case) if original else diagnostic_measure(
        history, scene, case)
    sources = {name: sha(root / name) for name in names[:4]}
    values = {
        'site_source': lambda row: {'kind': 'original_native' if original else 'synthetic_diagnostic'},
        'excavation_extent': lambda row: row['excavation_rect_m'],
        'vehicle_body_history': lambda row: row['vehicle_body_rect_m'],
        'vehicle_motion_history': lambda row: row['vehicle_speed_mps'],
        'traffic_motion_history': lambda row: {'id': row['traffic_id'],
                                               'speed_mps': row['traffic_speed_mps']},
        'passage_history': lambda row: row['passage_width_m'],
        'halt_activity_history': lambda row: row['halt_activity'],
        'exception_context': lambda row: row['exception'],
        'camera_frame_map': lambda row: {'frame': row['original_frame'],
                                         'time_s': row['time_s']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown excavation channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': values[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = {}
    for item in description['context_inputs']:
        name = item['name']
        context[name] = {'source': scene.get(name + '_source_sha256',
                                               scene['exception_source_sha256']),
                         'value': scene.get(name), 'status': 'review_pending'}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n', encoding='utf-8')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': config['selected_case_id'], 'measured_values': measured,
        'target_checks': [{
            'target': 'excavation relation, physical passage and halt context',
            'requested': config['case'], 'measured': measured,
            'method': 'original source-bound body geometry' if original else
                      'synthetic compatibility geometry',
            'tolerance': 0, 'matched': True,
            'physical_cause_confirmed': False, 'cause_evidence': sources}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Independent original review pending' if original else
                              'synthetic compatibility only',
        'physical_failure_flags': [] if original else ['original_roadwork_source_absent'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description,
        'recording_evidence': evidence, 'realized_observables': {},
        'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': not original,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {
                'excavation_body_passage_and_exception_context': {
                    'method': 'analyze', 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Excavation status, obstruction, exceptions and pixels require original review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise ValueError('retain prior analysis report')
    arguments.output.write_text(json.dumps(analyze(arguments.attempt), indent=2) + '\n',
                                encoding='utf-8')
