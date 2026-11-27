"""Saved-only safety-zone finalizer; physical overlap is not a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from zone_motion import CASES, center, intersection_area, measure_original, validate_scene

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def lines(path: Path) -> list[dict]:
    return [json.loads(value) for value in path.read_text(encoding='utf-8').splitlines() if value]


def verify_join(history: list[dict], mapping: list[dict], trace: list[dict]) -> None:
    if len(history) != len(mapping) or len(history) != len(trace):
        raise ValueError('safety-zone, trace and camera frame counts differ')
    for row, camera, telemetry in zip(history, mapping, trace):
        if ((row['original_frame'], row['time_s']) != (camera['carla_frame'], camera['time_s']) or
                (row['original_frame'], row['time_s']) != (telemetry['frame'], telemetry['time_s'])):
            raise ValueError('original safety-zone, trace and camera frames disagree')


def diagnostic_measure(history: list[dict], scene: dict, case) -> dict:
    validate_scene(scene, case)
    if len(history) < 3:
        raise ValueError('case-specific diagnostic history missing')
    identities = {row.get('vehicle_id') for row in history}
    if len(identities) != 1 or None in identities:
        raise ValueError('diagnostic vehicle identity changed')
    areas = []
    terminal_inside = False
    for row in history:
        for name in ('frame', 'vehicle_body', 'vehicle_motion', 'zone_boundary',
                     'designation', 'marking_visibility'):
            if not row.get(name + '_source_sha256'):
                raise ValueError('diagnostic source shape missing: ' + name)
        if (row['zone_boundary_source_sha256'] != scene['zone_boundary_source_sha256'] or
                row['designation_source_sha256'] != scene['designation_source_sha256']):
            raise ValueError('diagnostic zone or designation changed')
        area = intersection_area(row['vehicle_body_rect_m'], scene['zone_rect_m'])
        if abs(row['zone_overlap_area_m2'] - area) > .001:
            raise ValueError('diagnostic body/zone geometry mismatch')
        areas.append(area)
    x, y = center(history[-1]['vehicle_body_rect_m'])
    zone = scene['zone_rect_m']
    terminal_inside = zone[0] < x < zone[2] and zone[1] < y < zone[3]
    if (any(area > 0 for area in areas) != (case.route != 'beside') or
            terminal_inside != (case.route == 'within')):
        raise ValueError('diagnostic route differs from exact case')
    return {'case_id': case.name, 'frame_count': len(history),
            'overlap_frame_count': sum(area > 0 for area in areas),
            'terminal_center_within': terminal_inside,
            'official_designation_status': case.designation,
            'legal_judgment': None, 'diagnostic_fixture': True}


def analyze(attempt: Path) -> dict:
    root = Path(attempt)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case = next((item for item in CASES if config['selected_case_id'].endswith('__' + item.name)), None)
    if case is None:
        raise ValueError('exact safety-zone case missing')
    description = config['case']['recording_description']
    original = (root / 'acquisition.json').is_file()
    names = ('safety-zone-history.jsonl', 'safety-zone-site.json', 'trace.jsonl',
             'video_frames.jsonl', 'road.xodr', 'carla_recorder.log',
             *[name + '.mkv' for name in CAMERAS])
    if original:
        acquisition = json.loads(required(root, 'acquisition.json').read_text(encoding='utf-8'))
        for name in names:
            if (acquisition.get(name, {}).get('kind') != 'original_native' or
                    acquisition[name].get('sha256') != sha(required(root, name))):
                raise ValueError('original Native source changed: ' + name)
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text(encoding='utf-8'))
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture') is not False:
            raise ValueError('original Native provenance missing')
    else:
        note = json.loads(required(root, 'diagnostic-source-note.json').read_text(encoding='utf-8'))
        if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
                note.get('accepted_original_source') is not False or
                note.get('case_id') != config['selected_case_id']):
            raise ValueError('synthetic compatibility provenance missing')
    packet = json.loads(required(root, 'safety-zone-site.json').read_text(encoding='utf-8'))
    scene = packet['scene']
    validate_scene(scene, case)
    history = lines(required(root, 'safety-zone-history.jsonl'))
    mapping = lines(required(root, 'video_frames.jsonl'))
    trace = lines(required(root, 'trace.jsonl'))
    verify_join(history, mapping, trace)
    measured = measure_original(history, scene, case) if original else diagnostic_measure(history, scene, case)
    sources = {name: sha(root / name) for name in names[:4]}
    values = {
        'reviewed_site_source': lambda row: {'kind': 'original_native' if original else 'synthetic_diagnostic'},
        'highway_public_access': lambda row: scene['highway_public_access'],
        'public_authority_dedication': lambda row: scene['highway_dedicated_public_authority'],
        'official_pedestrian_exclusive_designation': lambda row: scene['official_pedestrian_exclusive'] if scene['official_pedestrian_exclusive'] is not None else 'unverified',
        'designation_interval': lambda row: scene['designation_interval_s'] if scene['designation_interval_s'] is not None else 'unverified',
        'zone_boundary': lambda row: scene['zone_rect_m'],
        'marking_or_sign': lambda row: scene['marking_or_sign_visible'] if scene['marking_or_sign_visible'] is not None else 'unverified',
        'marking_visibility_history': lambda row: row['marking_visibility_source_sha256'],
        'vehicle_classification': lambda row: scene['motor_vehicle'],
        'driver_attribution': lambda row: scene['driver_present'],
        'vehicle_body_history': lambda row: row['vehicle_body_rect_m'],
        'vehicle_motion_history': lambda row: row['vehicle_speed_mps'],
        'zone_overlap_history': lambda row: row['zone_overlap_area_m2'],
        'camera_frame_map': lambda row: {'frame': row['original_frame'], 'time_s': row['time_s']},
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown safety-zone channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'], 'value': values[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    context = {item['name']: {'source': scene.get(item['name'] + '_source_sha256'),
                              'value': scene.get(item['name']), 'status': 'review_pending'}
               for item in description['context_inputs']}
    context_path = root / 'channel-context.json'
    context_path.write_text(json.dumps(context) + '\n', encoding='utf-8')
    for item in description['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'], 'reference': context_path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {
        'case_id': config['selected_case_id'], 'measured_values': measured,
        'target_checks': [{'target': 'body motion relative to sourced safety-zone boundaries',
                           'requested': config['case'], 'measured': measured,
                           'method': 'original body geometry' if original else 'synthetic compatibility geometry',
                           'tolerance': 0, 'matched': True, 'physical_cause_confirmed': False,
                           'cause_evidence': sources}],
        'setup_confirmed': False, 'behavior_attempted': False, 'maneuver_completed': False,
        'termination_reason': 'Independent original review pending' if original else 'synthetic compatibility only',
        'physical_failure_flags': [] if original else ['original_official_zone_source_absent'],
        'trace_reference': 'trace.jsonl', 'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl', 'recording_description': description,
        'recording_evidence': evidence, 'realized_observables': {}, 'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
    }
    result = physical_result(root, result)
    write_result(root, result)
    return {
        'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
        'analysis_complete': True, 'diagnostic_fixture': not original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'measurements': {'safety_zone_original_body_motion': {
            'method': 'analyze', 'value': measured, 'sources': sources}},
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'limitations': ['Official designation, continuing marking visibility, actual motion and pixels require independent original review.'],
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n', encoding='utf-8')
