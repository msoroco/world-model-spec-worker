"""Saved-only original or synthetic two-vehicle tunnel finalization."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tunnel import CASES, inside_polygon, measure_original, validate_site

CAMERAS = ('overview', 'approach', 'tunnel_reference', 'driver_reference')


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
        raise ValueError('tunnel, trace and camera frame counts differ')
    for row, camera, telemetry in zip(history, mapping, trace):
        if ((row['original_frame'], row['time_s']) !=
                (camera['carla_frame'], camera['time_s']) or
                (row['original_frame'], row['time_s']) !=
                (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original tunnel, trace and camera frames disagree')


def diagnostic_measure(history, site, case):
    """Exercise geometry and source shape, without asserting original activity."""
    validate_site(site)
    if len(history) < 3:
        raise ValueError('case-specific diagnostic tunnel history missing')
    ego_ids = {row.get('ego_id') for row in history}
    other_ids = {row.get('other_vehicle_id') for row in history}
    if (len(ego_ids) != 1 or len(other_ids) != 1 or None in ego_ids | other_ids or
            ego_ids == other_ids):
        raise ValueError('diagnostic participant identity changed')
    for row in history:
        if (row.get('requested_activity') != case.activity or
                row.get('requested_exception_probe') != case.exception_probe or
                row.get('highway_source_sha256') != site['highway_source_sha256'] or
                row.get('tunnel_source_sha256') != site['tunnel_source_sha256'] or
                row.get('portal_source_sha256') != site['portal_source_sha256']):
            raise ValueError('diagnostic tunnel activity, exception or site changed')
        for name in ('source', 'map_source', 'ego_control_source'):
            if not row.get(name + '_sha256'):
                raise ValueError('diagnostic original-source shape missing: ' + name)
        if row.get('ego_speed_mps', 100) > .1 or not row.get('ego_body_vertices_xy'):
            raise ValueError('diagnostic terminal halt missing')
        if row.get('other_vehicle_purpose') not in ('travel', 'obstacle', 'unknown'):
            raise ValueError('diagnostic other-vehicle purpose missing')
        if case.exception_probe and not row.get('exception_source_sha256'):
            raise ValueError('diagnostic exception source absent')
    terminal_inside = all(inside_polygon(vertex, site['tunnel_polygon_xy'])
                          for vertex in history[-1]['ego_body_vertices_xy'])
    return {
        'case_id': case.case_id, 'frame_count': len(history),
        'ego_id': next(iter(ego_ids)), 'other_vehicle_id': next(iter(other_ids)),
        'requested_activity': case.activity,
        'requested_endpoint': case.endpoint,
        'requested_exception_probe': case.exception_probe,
        'ego_halt_observed': True,
        'terminal_body_inside_tunnel': terminal_inside,
        'terminal_body_outside_tunnel': not terminal_inside,
        'activity_judgment': 'unresolved', 'exception_judgment': 'unresolved',
        'legal_judgment': None, 'diagnostic_fixture': True}


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = next((item for item in CASES
                 if config['selected_case_id'].endswith('__' + item.case_id)), None)
    if case is None:
        raise ValueError('exact tunnel case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('tunnel-history.jsonl', 'tunnel-site.json', 'trace.jsonl',
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
    packet = json.loads(required(root, 'tunnel-site.json').read_text())
    site = packet['site']
    validate_site(site)
    history = lines(required(root, 'tunnel-history.jsonl'))
    mapping = lines(required(root, 'video_frames.jsonl'))
    trace = lines(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    measured = measure_original(history, site, case) if original else diagnostic_measure(
        history, site, case)
    sources = {name: sha(root / name) for name in names[:4]}
    values = {
        'site_source': lambda row: {'kind': 'original_native' if original else 'synthetic_diagnostic'},
        'tunnel_boundary': lambda row: site['tunnel_polygon_xy'],
        'ego_body_footprint': lambda row: row['ego_body_vertices_xy'],
        'ego_motion_history': lambda row: row['ego_speed_mps'],
        'other_vehicle_motion_history': lambda row: row['other_vehicle_speed_mps'],
        'other_vehicle_purpose': lambda row: row['other_vehicle_purpose'],
        'halt_activity_history': lambda row: row['requested_activity'],
        'exception_context': lambda row: {'probe': row['requested_exception_probe'],
                                          'source': row.get('exception_source_sha256')},
        'camera_frame_map': lambda row: {'frame': row['original_frame'],
                                         'time_s': row['time_s']}}
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown tunnel channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                           'value': values[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = {item['name']: {
        'source': packet.get('sources', {}).get('authority', {}).get('sha256'),
        'value': packet.get(item['name']), 'status': 'review_pending'}
        for item in description['context_inputs']}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n', encoding='utf-8')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': config['selected_case_id'], 'measured_values': measured,
        'target_checks': [{
            'target': 'full-body highway-tunnel relation and halt context',
            'requested': config['case'], 'measured': measured,
            'method': 'original source-bound tunnel and two-vehicle geometry' if original else
                      'synthetic compatibility geometry',
            'tolerance': 0,
            'matched': measured['terminal_body_inside_tunnel'] if case.endpoint == 'inside_tunnel'
                       else measured['terminal_body_outside_tunnel'],
            'physical_cause_confirmed': False, 'cause_evidence': sources}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': 'Independent original review pending' if original else
                              'synthetic compatibility only',
        'physical_failure_flags': [] if original else ['original_tunnel_source_absent'],
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
                'tunnel_body_halt_and_exception_context': {
                    'method': 'analyze', 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Highway tunnel, activity, exceptions and pixels require original review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n',
                           encoding='utf-8')
