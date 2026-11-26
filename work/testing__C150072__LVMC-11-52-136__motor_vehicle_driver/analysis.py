"""Saved-only access-aisle measurement; diagnostic and original source paths are separate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from access_aisle import CASES, intersection_area, measure_original, validate_site

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
        raise ValueError('exact access-aisle case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text())
        names = ('access-aisle-history.jsonl', 'access-aisle-site.json', 'trace.jsonl',
                 'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
                 *[name + '.mkv' for name in CAMERAS])
        for name in names:
            if acquisition.get(name, {}).get('kind') != 'original_native' or acquisition[name].get('sha256') != sha(required(root, name)):
                raise ValueError('original Native source changed: ' + name)
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
        site = json.loads(required(root, 'access-aisle-site.json').read_text())
        history = rows(required(root, 'access-aisle-history.jsonl'))
        mapping = rows(required(root, 'video_frames.jsonl'))
        trace = rows(required(root, 'trace.jsonl'))
        verify_join(history, mapping, trace)
        measured = measure_original(history, site, case)
        sources = {name: acquisition[name]['sha256'] for name in
                   ('access-aisle-history.jsonl', 'access-aisle-site.json',
                    'video_frames.jsonl', 'trace.jsonl')}
    else:
        marker = json.loads(required(root, 'diagnostic-source-note.json').read_text())
        if marker.get('source_kind') != 'synthetic_diagnostic_fixture' or marker.get('accepted_original_source') is not False:
            raise ValueError('synthetic compatibility provenance missing')
        site_path = required(root, 'access-aisle-site.json')
        site = json.loads(site_path.read_text())
        validate_site(site)
        history = rows(required(root, 'access-aisle-history.jsonl'))
        mapping = rows(required(root, 'video_frames.jsonl'))
        trace = rows(required(root, 'trace.jsonl'))
        verify_join(history, mapping, trace)
        if len(history) < 3 or any(row['observed_activity'] not in ('park', 'loading_stop', 'travel') for row in history):
            raise ValueError('case-specific diagnostic aisle history missing')
        overlaps = [intersection_area(row['vehicle_body_polygon_xy'], site['aisle_polygon_xy']) for row in history]
        measured = {'case_id': suffix, 'frame_count': len(history),
                    'terminal_mean_aisle_body_overlap_m2': sum(overlaps[-3:]) / 3,
                    'observed_activity': history[-1]['observed_activity'],
                    'parking_judgment': 'unresolved', 'legal_judgment': None,
                    'diagnostic_fixture': True}
        if measured['observed_activity'] != case.requested_activity:
            raise ValueError('diagnostic activity differs from exact case')
        if (case.target == 'adjacent_space') != (measured['terminal_mean_aisle_body_overlap_m2'] == 0):
            raise ValueError('diagnostic vehicle body differs from exact footprint')
        sources = {'access-aisle-site.json': sha(site_path),
                   'access-aisle-history.jsonl': sha(root / 'access-aisle-history.jsonl'),
                   'video_frames.jsonl': sha(root / 'video_frames.jsonl'),
                   'trace.jsonl': sha(root / 'trace.jsonl')}
    channel_values = {
        'site_source': lambda row: {'source_kind': 'original_native' if original else 'synthetic_diagnostic'},
        'aisle_polygon': lambda row: site['aisle_polygon_xy'],
        'adjacent_space_polygon': lambda row: site['adjacent_space_polygon_xy'],
        'body_footprint_history': lambda row: row['vehicle_body_polygon_xy'],
        'ego_speed_history': lambda row: row['ego_speed_mps'],
        'activity_history': lambda row: row['observed_activity'],
        'camera_frame_map': lambda row: {'frame': row['original_frame'], 'time_s': row['time_s']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in channel_values:
            raise ValueError('unknown access-aisle channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': channel_values[name](row)}) + '\n'
                                for row in history))
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps({
        'jurisdiction': {'source': site.get('jurisdiction_source_sha256'), 'status': 'review_pending'},
        'qualifying_aisle_markings': {'source': site.get('aisle_marking_source_sha256'), 'status': 'review_pending'},
        'accessible_route_design': {'source': site.get('accessible_route_source_sha256'), 'status': 'review_pending'},
        'activity_purpose': {'source': site.get('sources', {}).get('activity_plan'), 'status': 'review_pending'}}) + '\n')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'], 'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': config['selected_case_id'], 'measured_values': measured,
              'target_checks': [{'target': 'observed access-aisle body and activity',
                                 'requested': config['case'], 'measured': measured,
                                 'method': 'original source-bound geometry' if original else 'synthetic compatibility geometry',
                                 'tolerance': 0, 'matched': True,
                                 'physical_cause_confirmed': False, 'cause_evidence': sources}],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'Original independent review pending' if original else 'synthetic compatibility only',
              'physical_failure_flags': [] if original else ['original_qualifying_aisle_absent'],
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
            'measurements': {'access_aisle_footprint_activity': {'method': 'analyze',
                                                                 'value': measured, 'sources': sources}},
            'physical_checks': result['physical_checks'],
            'realized_observables': result['realized_observables'],
            'limitations': ['Aisle designation, actual parking conduct and pixels require original independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n')
