"""Saved-only source-bound roadside signal and body-distance finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from signal_approach import CASE_BY_ID, measure_original, signed_body_station, unit_route, station, validate_scene

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
        raise ValueError('signal, trace and camera frame counts differ')
    for row, camera, telemetry in zip(history, mapping, trace):
        if ((row['original_frame'], row['time_s']) !=
                (camera['carla_frame'], camera['time_s']) or
                (row['original_frame'], row['time_s']) !=
                (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original signal, trace and camera frames disagree')


def diagnostic_measure(history, scene, case):
    """Check short fixture shape without calling it physical evidence."""
    validate_scene(scene, case)
    if len(history) < 3:
        raise ValueError('case-specific diagnostic history missing')
    frames = [row['original_frame'] for row in history]
    if len(set(frames)) != len(frames):
        raise ValueError('diagnostic frames repeat')
    origin, heading = unit_route(scene)
    signal_station = station(scene['signal_xy'], origin, heading)
    gaps = []
    for row in history:
        if (row.get('signal_id') != scene['signal_id'] or
                row.get('activity') != case.activity or
                row.get('exception') != case.exception or
                row.get('signal_source_sha256') != scene['signal_source_sha256'] or
                not row.get('signal_indication')):
            raise ValueError('diagnostic signal/activity source changed')
        for field in ('frame', 'signal', 'highway', 'authority', 'traffic'):
            if not row.get(field + '_source_sha256'):
                raise ValueError('diagnostic source shape missing: ' + field)
        gaps.append(signed_body_station(row['body_vertices_xy_m'], origin,
                                        heading, signal_station))
    return {'case_id': scene['case_id'], 'frame_count': len(history),
            'terminal_body_front_approach_gap_m': gaps[-1]['body_front_approach_gap_m'],
            'terminal_body_rear_approach_gap_m': gaps[-1]['body_rear_approach_gap_m'],
            'raw_body_gap_history_m': gaps,
            'statutory_quantity_m': 9.144,
            'legal_measurement_datum': 'unresolved',
            'diagnostic_fixture': True,
            'physical_acceptance_claimed': False}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = CASE_BY_ID.get(config['selected_case_id'])
    if case is None:
        raise ValueError('exact roadside-signal case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('signal-history.jsonl', 'signal-site.json', 'trace.jsonl',
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
    packet = json.loads(required(root, 'signal-site.json').read_text())
    scene = packet['scene']
    validate_scene(scene, case)
    history = lines(required(root, 'signal-history.jsonl'))
    mapping = lines(required(root, 'video_frames.jsonl'))
    trace = lines(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    measured = measure_original(history, scene, case) if original else diagnostic_measure(
        history, scene, case)
    sources = {name: sha(root / name) for name in names[:4]}
    values = {
        'highway_public_use_and_route': lambda row: scene['highway_public_use_reviewed'],
        'signal_placement_and_authority': lambda row: {'signal_id': row['signal_id'],
                                                        'status': case.signal_status},
        'signal_indication_history': lambda row: row['signal_indication'],
        'vehicle_body_and_motion_history': lambda row: {'body_vertices_xy_m': row['body_vertices_xy_m'],
                                                         'speed_mps': row['ego_speed_mps']},
        'signed_approach_station_and_raw_distance': lambda row: measured['raw_body_gap_history_m'][history.index(row)] if not original else measured['body_gap_history_m'][history.index(row)],
        'halt_activity_and_occupancy': lambda row: {'activity': row['activity'],
                                                    'ego_actor_id': row['ego_actor_id']},
        'traffic_conflict_history': lambda row: {'traffic_actor_id': row['traffic_actor_id'],
                                                 'speed_mps': row['traffic_speed_mps']},
        'law_officer_device_direction': lambda row: row['exception'],
        'four_camera_frame_map': lambda row: {'frame': row['original_frame'],
                                              'time_s': row['time_s']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown roadside-signal channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': values[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = {item['name']: {'source': scene.get(item['name'] + '_source_sha256',
                                                     scene['authority_source_sha256']),
                              'value': scene.get(item['name']), 'status': 'review_pending'}
               for item in description['context_inputs']}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n', encoding='utf-8')
    evidence.extend({'name': item['name'], 'unit': item['unit'],
                     'reference': context_path.name} for item in description['context_inputs'])
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': config['selected_case_id'], 'measured_values': measured,
        'target_checks': [{'target': 'roadside signal approach and halt',
                           'requested': config['case'], 'measured': measured,
                           'method': 'original source-bound body/signal geometry' if original else
                                     'synthetic compatibility geometry',
                           'tolerance': 0, 'matched': True,
                           'physical_cause_confirmed': False,
                           'cause_evidence': sources}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Independent original review pending' if original else
                              'synthetic compatibility only',
        'physical_failure_flags': [] if original else ['original_signal_source_absent'],
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
            'measurements': {'signal_body_and_exception_context': {
                'method': 'analyze', 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Signal official status, exception applicability and actual pixels require original review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n',
                           encoding='utf-8')
