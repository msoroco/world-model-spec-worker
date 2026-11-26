"""Saved-only rear signal measurement, separating original and diagnostic evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from rear_signal import CASES, measure_original, validate_scene

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line]


def verify_join(history, mapping, trace):
    if len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError('participant, trace and camera frame counts differ')
    for participant, camera, telemetry in zip(history, mapping, trace):
        if ((participant['original_frame'], participant['time_s']) !=
                (camera['carla_frame'], camera['time_s']) or
                (participant['original_frame'], participant['time_s']) !=
                (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original participant, trace and camera frames disagree')


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    suffix = config['selected_case_id'].split('__')[-1]
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None:
        raise ValueError('exact rear-signal case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text())
        names = ('rear-signal-history.jsonl', 'rear-signal-scene.json', 'trace.jsonl',
                 'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name in CAMERAS])
        for name in names:
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(required(root, name))):
                raise ValueError('original Native source changed: ' + name)
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
        scene = json.loads(required(root, 'rear-signal-scene.json').read_text())
        history = rows(required(root, 'rear-signal-history.jsonl'))
        mapping = rows(required(root, 'video_frames.jsonl'))
        trace = rows(required(root, 'trace.jsonl'))
        verify_join(history, mapping, trace)
        measured = measure_original(history, scene, case)
        sources = {name: acquisition[name]['sha256'] for name in
                   ('rear-signal-history.jsonl', 'rear-signal-scene.json',
                    'video_frames.jsonl', 'trace.jsonl')}
    else:
        marker = json.loads(required(root, 'diagnostic-source-note.json').read_text())
        if (marker.get('source_kind') != 'synthetic_diagnostic_fixture' or
                marker.get('accepted_original_source') is not False):
            raise ValueError('synthetic compatibility provenance missing')
        scene = json.loads(required(root, 'rear-signal-scene.json').read_text())
        validate_scene(scene)
        history = rows(required(root, 'rear-signal-history.jsonl'))
        mapping = rows(required(root, 'video_frames.jsonl'))
        trace = rows(required(root, 'trace.jsonl'))
        verify_join(history, mapping, trace)
        if len(history) < 3 or not all(row.get('ego_id') and row.get('rear_id') and
                                       row.get('signal_displayed') in (True, False) and
                                       row.get('rear_driver_present') is case.rear_driver
                                       for row in history):
            raise ValueError('case-specific diagnostic rear-signal history missing')
        measured = {'case_id': suffix, 'frame_count': len(history),
                    'signal_precedes_event': case.signal_policy == 'before',
                    'rear_driver_present': case.rear_driver,
                    'maneuver': case.maneuver, 'diagnostic_fixture': True,
                    'signal_appropriateness_judgment': None,
                    'immediately_to_rear_judgment': None, 'legal_judgment': None}
        sources = {name: sha(root / name) for name in
                   ('rear-signal-history.jsonl', 'rear-signal-scene.json',
                    'video_frames.jsonl', 'trace.jsonl')}
    fields = {
        'scene_source': lambda row: {'source_kind': 'original_native' if original else 'synthetic_diagnostic'},
        'one_way_route': lambda row: scene['route_xy'],
        'ego_motion': lambda row: row['ego_speed_mps'],
        'rear_motion': lambda row: row['rear_speed_mps'],
        'rear_driver': lambda row: row['rear_driver_present'],
        'rear_relation': lambda row: {'gap_m': row['rear_longitudinal_gap_m'],
                                      'offset_m': row['rear_lateral_offset_m']},
        'signal_display': lambda row: row['signal_displayed'],
        'rear_signal_visibility': lambda row: row['signal_visible_from_rear'],
        'maneuver_event': lambda row: {'onset': row['event_marker']},
        'camera_frame_map': lambda row: {'frame': row['original_frame'], 'time_s': row['time_s']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in fields:
            raise ValueError('unknown rear-signal channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': fields[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = root / 'channel-context.json'
    contexts = {name: {'source': scene.get(name + '_source_sha256'),
                       'status': 'review_pending'}
                for name in ('jurisdiction', 'ego_driver_control', 'signal_device',
                             'conflict_context', 'official_direction_context')}
    contexts['rear_driver_presence'] = {
        'source': scene['rear_vehicle']['driver_source_sha256'],
        'present': scene['rear_vehicle']['driver_present'],
        'status': 'review_pending'}
    context.write_text(json.dumps(contexts) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'], 'reference': context.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'original stop/decrease and signal order with rear participant',
                                 'requested': config['case'], 'measured': measured,
                                 'method': 'original source-bound participant history' if original else
                                           'synthetic compatibility history',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original independent review pending' if original else
                                    'synthetic compatibility only',
              'physical_failure_flags': [] if original else ['original_rear_driver_and_signal_absent'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': description, 'recording_evidence': evidence,
              'realized_observables': {}, 'diagnostic_fixture': not original,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'diagnostic_fixture': not original,
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
            'measurements': {'rear_signal_order_and_recipient': {'method': 'analyze',
                                                                 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Actual rear driver, signal pixels, appropriateness, immediacy and legal outcome need original independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
