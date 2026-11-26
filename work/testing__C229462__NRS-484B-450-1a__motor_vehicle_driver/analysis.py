"""Saved-only original or diagnostic sidewalk body and context analysis."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from sidewalk_case import CASES, area_intersection, boundary_distance, measure_original, validate_site

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
        raise ValueError('body, trace and camera frame counts differ')
    for body, camera, telemetry in zip(history, mapping, trace):
        if ((body['original_frame'], body['time_s']) != (camera['carla_frame'], camera['time_s']) or
                (body['original_frame'], body['time_s']) != (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original body, trace and camera frames disagree')


def analyze(attempt):
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text())
    suffix = config['selected_case_id'].split('__')[-1]
    case = next((item for item in CASES if item.case_id == suffix), None)
    if case is None:
        raise ValueError('exact sidewalk case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('sidewalk-history.jsonl', 'sidewalk-site.json', 'trace.jsonl',
             'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
             *[name + '.mkv' for name in CAMERAS])
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text())
        for name in names:
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(required(root, name))):
                raise ValueError('original Native source changed: ' + name)
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
    else:
        marker = json.loads(required(root, 'diagnostic-source-note.json').read_text())
        if (marker.get('source_kind') != 'synthetic_diagnostic_fixture' or
                marker.get('accepted_original_source') is not False or
                marker.get('case_id') != config['selected_case_id']):
            raise ValueError('synthetic compatibility provenance missing')
    site_path = required(root, 'sidewalk-site.json')
    site = json.loads(site_path.read_text())
    validate_site(site)
    if (site['requested_relation'] != case.relation or
            site['exception_context']['traffic_conflict_necessity'] != case.traffic_context):
        raise ValueError('reviewed sidewalk target or exception context differs')
    history = rows(required(root, 'sidewalk-history.jsonl'))
    mapping = rows(required(root, 'video_frames.jsonl'))
    trace = rows(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    if original:
        measured = measure_original(history, site, case)
    else:
        if len(history) < 3 or any(row.get('observed_activity') != 'park' for row in history):
            raise ValueError('case-specific diagnostic parking history missing')
        if any(row.get('exception_context') != site['exception_context'] for row in history):
            raise ValueError('diagnostic exception context changed')
        if case.traffic_context == 'unresolved' and any(not row.get('conflict_vehicle_id') for row in history):
            raise ValueError('diagnostic conflict actor absent')
        areas = [area_intersection(row['vehicle_body_polygon_xy'], site['sidewalk_polygon_xy']) for row in history]
        distances = [boundary_distance(row['vehicle_body_polygon_xy'], site['sidewalk_polygon_xy']) for row in history]
        overlap = sum(areas[-3:]) / 3
        distance = min(distances[-3:])
        if (case.relation == 'overlap' and overlap <= 0 or
                case.relation != 'overlap' and overlap > 0 or
                case.relation == 'touch' and distance > .05 or
                case.relation == 'separate' and distance <= .05):
            raise ValueError('diagnostic body footprint differs from case')
        measured = {'case_id': suffix, 'frame_count': len(history),
                    'terminal_mean_sidewalk_body_overlap_m2': overlap,
                    'terminal_boundary_distance_m': distance,
                    'observed_activity': 'park',
                    'traffic_conflict_necessity': case.traffic_context,
                    'exception_context': site['exception_context'],
                    'sidewalk_status_judgment': None, 'traffic_necessity_judgment': None,
                    'legal_judgment': None, 'diagnostic_fixture': True}
    sources = {name: sha(root / name) for name in ('sidewalk-site.json', 'sidewalk-history.jsonl',
                                                   'video_frames.jsonl', 'trace.jsonl')}
    channel_values = {
        'site_source': lambda row: {'kind': 'original_native' if original else 'synthetic_diagnostic'},
        'sidewalk_polygon': lambda row: site['sidewalk_polygon_xy'],
        'vehicle_body_history': lambda row: row['vehicle_body_polygon_xy'],
        'ego_speed_history': lambda row: row['ego_speed_mps'],
        'activity_history': lambda row: row['observed_activity'],
        'exception_context': lambda row: row['exception_context'],
        'conflict_motion': lambda row: {'id': row.get('conflict_vehicle_id'),
                                        'speed_mps': row.get('conflict_speed_mps'),
                                        'source': row.get('conflict_motion_source_sha256')},
        'camera_frame_map': lambda row: {'frame': row['original_frame'], 'time_s': row['time_s']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('unknown sidewalk channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': channel_values[name](row)}) + '\n'
                                for row in history))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = {}
    for item in description['context_inputs']:
        name = item['name']
        value = site['exception_context'][name] if name in site['exception_context'] else site.get(name)
        context[name] = {'source': site.get(name + '_source_sha256', site.get('exception_context_source_sha256')),
                         'value': value, 'status': 'review_pending'}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'], 'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'observed sidewalk body, parking and context',
                                 'requested': config['case'], 'measured': measured,
                                 'method': 'original source-bound geometry' if original else 'synthetic compatibility geometry',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original independent review pending' if original else 'synthetic compatibility only',
              'physical_failure_flags': [] if original else ['original_sidewalk_source_absent'],
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
            'measurements': {'sidewalk_body_placement_and_context': {'method': 'analyze',
                                                                    'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Sidewalk status, exceptions and pixels require original independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
