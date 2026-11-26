"""Saved hydrant measurement from sealed Native or explicit synthetic sources.

This reports observed target-side body gap and source context. It does not make
a legal distance, exception, physical visibility or compliance finding.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hydrant import ASSIGNMENT, CASES, measure_original_history
from native_packet import validate_packet
from native_runner import CAMERAS, FRAMES, sha


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def measure_hydrant_distance(site: dict, history: list, case) -> dict:
    return measure_original_history(history, site, case)


def original(root: Path, case_id: str):
    seal_path = required(root, 'capture-seal.json')
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if (seal.get('format') != 'worker-sealed-capture' or
            seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or
            seal.get('frames') != FRAMES or
            seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified'] or
            seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('sealed original Native hydrant capture required')
    files = seal.get('sources')
    mandatory = {'site.json', 'original-hydrant-history.jsonl',
                 'camera-frame-map.jsonl', 'video_frames.jsonl',
                 'reviewed-packet/reviewed-site.json',
                 *[name + '.mkv' for name in CAMERAS]}
    if not isinstance(files, dict) or not mandatory <= set(files):
        raise ValueError('sealed original hydrant source inventory incomplete')
    for name, digest in files.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or sha(required(root, name)) != digest:
            raise ValueError('sealed original source changed: ' + name)
    revision = seal.get('native_revision', {})
    if (revision.get('construction_sha256') != sha(required(root, 'construction.json')) or
            revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
        raise ValueError('sealed Native implementation changed')
    packet_path = required(root, 'reviewed-packet/reviewed-site.json')
    reviewed_site, _, _, _ = validate_packet(packet_path, case_id)
    site_path = required(root, 'site.json')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if site != reviewed_site:
        raise ValueError('original reviewed site differs')
    return site, {'site.json': sha(site_path),
                  'original-hydrant-history.jsonl': sha(required(root, 'original-hydrant-history.jsonl')),
                  'capture-seal.json': sha(seal_path)}


def diagnostic(root: Path, case_id: str):
    note_path = required(root, 'diagnostic-source-note.json')
    note = json.loads(note_path.read_text(encoding='utf-8'))
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
            note.get('accepted_original_source') is not False or
            note.get('case_id') != case_id):
        raise ValueError('explicit synthetic hydrant diagnostic provenance required')
    site_path = required(root, 'site.json')
    return json.loads(site_path.read_text(encoding='utf-8')), {
        'site.json': sha(site_path),
        'original-hydrant-history.jsonl': sha(required(root, 'original-hydrant-history.jsonl')),
        'diagnostic-source-note.json': sha(note_path)}


def check_joins(root: Path, history: list):
    cameras = rows(required(root, 'camera-frame-map.jsonl'))
    videos = rows(required(root, 'video_frames.jsonl'))
    if len(history) != FRAMES or len(cameras) != FRAMES or len(videos) != FRAMES:
        raise ValueError('full original hydrant and camera history required')
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        frame = row['frame']
        if (camera.get('frame_index') != index or camera.get('native_frame') != frame or
                camera.get('camera_frames') != {name: frame for name in CAMERAS} or
                video.get('video_frame') != index or video.get('carla_frame') != frame or
                video.get('native_frame', video.get('carla_frame')) != frame or
                abs(camera.get('time_s', -100) - row['time_s']) > 1e-5 or
                abs(video.get('time_s', -100) - row['time_s']) > 1e-5):
            raise ValueError('original hydrant/camera/native frame join changed')


def analyze(root: str | Path) -> dict:
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    matches = [case for case in CASES if ASSIGNMENT + '__' + case.suffix == case_id]
    if config.get('assignment_id') != ASSIGNMENT or len(matches) != 1:
        raise ValueError('saved exact hydrant assignment differs')
    case = matches[0]
    is_original = (root / 'capture-seal.json').is_file()
    site, source = original(root, case_id) if is_original else diagnostic(root, case_id)
    history = rows(required(root, 'original-hydrant-history.jsonl'))
    check_joins(root, history)
    measured = measure_hydrant_distance(site, history, case)
    description = config['case']['recording_description']
    values = {
        'longitudinal_hydrant_gap': lambda row: {'side': row['side'],
            'body_gap_m': row['longitudinal_body_hydrant_gap_m']},
        'parallel_parking_authority': lambda row: {
            'permitted': site['parallel_parking_permitted'],
            'source_sha256': site['parallel_parking_authority_sha256']},
        'vehicle_activity': lambda row: row['activity'],
        'exception_source': lambda row: {
            'kind': case.exception,
            'source_sha256': history[0].get('exception_source_sha256')},
        'camera_frame_identity': lambda row: row['frame'],
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in values:
            raise ValueError('unknown hydrant recording channel: ' + name)
        channel_path = root / ('channel-' + name + '.jsonl')
        channel_path.write_text(''.join(json.dumps({'time_s': row['time_s'],
            'value': values[name](row)}) + '\n' for row in measured['observed']),
            encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': channel_path.name})
    from worker_exchange.native_output import physical_result, write_result
    gap = measured['minimum_longitudinal_gap_m']
    result = {'case_id': case_id,
        'measured_values': {'minimum_target_side_body_hydrant_gap_m': gap,
                            'target_activity_frames': measured['target_frame_count']},
        'target_checks': [{'target': 'source-measured target-side hydrant gap',
            'requested': case.gap_m, 'measured': gap,
            'method': '900 sealed original body rows' if is_original else '900 synthetic body rows',
            'tolerance': .05, 'matched': False if is_original else abs(gap - case.gap_m) <= .05,
            'physical_cause_confirmed': False, 'cause_evidence': source}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'termination_reason': 'saved measurement pending physical review',
        'physical_failure_flags': [] if is_original else ['original_hydrant_source_absent'],
        'trace_reference': 'trace.jsonl',
        'video_references': [name + '.mkv' for name in CAMERAS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}, 'diagnostic_fixture': not is_original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
        'analysis_complete': True, 'diagnostic_fixture': not is_original,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'measurements': {'hydrant_parallel_distance': {
            'method': 'measure_hydrant_distance',
            'value': {'minimum_target_side_gap_m': gap,
                      'target_activity_frames': measured['target_frame_count'],
                      'frame_count': measured['frame_count'],
                      'legal_distance_convention': 'unresolved_review'},
            'sources': source}},
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'limitations': ['Physical visibility, municipal permission, exception necessity and legal distance convention require independent original review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior hydrant analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n',
                           encoding='utf-8')
