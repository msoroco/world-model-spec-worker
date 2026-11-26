"""Saved-only original truck-following measurement; no legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from truck_following import CASES, audit_original_frames, audit_case_realization
from native_packet import AID, VIEWS

HISTORY = 'original-truck-history.jsonl'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def check_source(root, case_id):
    seal_path = root / 'capture-seal.json'
    if seal_path.is_file():
        seal = json.loads(seal_path.read_text(encoding='utf-8'))
        if (seal.get('format') != 'worker-sealed-capture' or
                seal.get('provenance_kind') != 'native' or
                seal.get('diagnostic_fixture') is not False or
                seal.get('frames') != 900 or
                seal.get('restoration', {}).get('restored') is not True):
            raise ValueError('sealed original Native truck capture required')
        files = seal.get('sources')
        mandatory = {HISTORY, 'camera-frame-map.jsonl', 'video_frames.jsonl',
                     *[view + '.mkv' for view in VIEWS]}
        if not isinstance(files, dict) or not mandatory <= set(files):
            raise ValueError('sealed original truck source inventory incomplete')
        for name, digest in files.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or sha(required(root, name)) != digest:
                raise ValueError('sealed original truck source changed: ' + name)
        revision = seal.get('native_revision', {})
        if (revision.get('construction_sha256') != sha(required(root, 'construction.json'))
                or revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
            raise ValueError('sealed Native implementation changed')
        return False, {HISTORY: sha(required(root, HISTORY)),
                       'capture-seal.json': sha(seal_path)}
    note_path = required(root, 'diagnostic-source-note.json')
    note = json.loads(note_path.read_text(encoding='utf-8'))
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture' or
            note.get('accepted_original_source') is not False or
            note.get('case_id') != case_id):
        raise ValueError('explicit synthetic truck diagnostic provenance required')
    return True, {HISTORY: sha(required(root, HISTORY)),
                  'diagnostic-source-note.json': sha(note_path)}


def check_joins(root, history):
    cameras = rows(required(root, 'camera-frame-map.jsonl'))
    videos = rows(required(root, 'video_frames.jsonl'))
    if len(history) != 900 or len(cameras) != 900 or len(videos) != 900:
        raise ValueError('full original truck and camera history required')
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        frame = row['native_frame']
        if (row['frame'] != index or camera.get('frame_index') != index
                or camera.get('native_frame') != frame
                or camera.get('camera_frames') != {view: frame for view in VIEWS}
                or video.get('video_frame') != index
                or video.get('carla_frame') != frame
                or abs(camera.get('time_s', -100) - row['time_s']) > 1e-5
                or abs(video.get('time_s', -100) - row['time_s']) > 1e-5):
            raise ValueError('truck/camera/native frame join changed')


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    matches = [case for case in CASES if case_id == AID + '__' + case.suffix]
    if config.get('assignment_id') != AID or len(matches) != 1:
        raise ValueError('saved exact truck-following assignment differs')
    diagnostic, source = check_source(root, case_id)
    history = rows(required(root, HISTORY))
    check_joins(root, history)
    measured = audit_original_frames({'source_kind': 'sealed_native_original_frames',
                                      'case_id': case_id, 'frames': history}, case_id=case_id)
    measured['original_source_sha256'] = source[HISTORY]
    # Construction realization is retained as a separate physical review target.
    try:
        realization = audit_case_realization(matches[0], measured, case_id=case_id)
    except ValueError as error:
        realization = {'construction_realized': False, 'gap': str(error),
                       'legal_judgment': 'unresolved'}
    description = config['case']['recording_description']
    channels = {
        'sealed_native_original_frames': lambda row: row['frame'],
        'original_body_vertices': lambda row: {b['identity']: b['route_vertex_s_m'] for b in row['bodies']},
        'full_mesh_width': lambda row: {b['identity']: b.get('overall_width_m') for b in row['bodies']},
        'map_lane_availability': lambda row: row['lane_source']['available_same_direction_lanes'],
        'vehicle_inventory': lambda row: [b['identity'] for b in row['bodies']],
        'controller_commands': lambda row: row.get('controller_commands', []),
        'video_four_views': lambda row: row['frame'],
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in channels:
            raise ValueError('unknown truck recording channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                            'value': channels[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case_id,
        'measured_values': {'steady_gap_min_m': measured['steady_gap_min_m'],
                            'subject_width_min_m': measured['subject_width_min_m'],
                            'lead_width_min_m': measured['lead_width_min_m']},
        'target_checks': [{'target': 'measured along-route full-body truck gap',
            'requested': matches[0].gap_target_m, 'measured': measured['steady_gap_min_m'],
            'method': '900 sealed original Native frames' if not diagnostic else '900 synthetic diagnostic frames',
            'tolerance': 3.0, 'matched': abs(measured['steady_gap_min_m'] - matches[0].gap_target_m) < 3.0,
            'physical_cause_confirmed': False, 'cause_evidence': source}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'termination_reason': 'saved measurement pending physical review',
        'physical_failure_flags': [] if not diagnostic else ['original_truck_source_absent'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': description, 'recording_evidence': evidence,
        'realized_observables': {}, 'diagnostic_fixture': diagnostic,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    result = physical_result(root, result)
    write_result(root, result)
    return {'format': 'worker-analysis-report', 'case_id': case_id,
        'analysis_complete': True, 'diagnostic_fixture': diagnostic,
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False,
        'measurements': {'truck_gap_width_lane_and_entry': {
            'method': 'audit_original_frames', 'value': measured, 'sources': source}},
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'realization': realization,
        'limitations': ['Original physical motion, pixels and conditions-permit/without-danger legal judgment require independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior truck analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n', encoding='utf-8')
