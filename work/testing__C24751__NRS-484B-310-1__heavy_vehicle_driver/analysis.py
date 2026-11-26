"""Saved-only flashing-red measurement; no legal or physical acceptance claim."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from flashing_red_native import ASSIGNMENT, CASES, measure_original as source_measure_original
from native_packet import validate_packet
from native_runner import CAMERAS, FRAMES, sha

HISTORY = 'original-flashing-red-history.jsonl'


def measure_original(history: list, site: dict, case) -> dict:
    return source_measure_original(history, site, case)


def required(root, name):
    path = Path(root) / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def original(root, case_id):
    seal_path = required(root, 'capture-seal.json')
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if (seal.get('format') != 'worker-sealed-capture'
            or seal.get('provenance_kind') != 'native'
            or seal.get('diagnostic_fixture') is not False
            or seal.get('frames') != FRAMES
            or seal.get('events') != ['capture_finished', 'encoders_closed',
                                      'restoration_verified']
            or seal.get('restoration', {}).get('restored') is not True):
        raise ValueError('sealed original Native flashing-red capture required')
    files = seal.get('sources')
    mandatory = {'site.json', HISTORY, 'camera-frame-map.jsonl',
                 'video_frames.jsonl', 'reviewed-packet/reviewed-site.json',
                 *[name + '.mkv' for name in CAMERAS]}
    if not isinstance(files, dict) or not mandatory <= set(files):
        raise ValueError('sealed original flashing-red source inventory incomplete')
    for name, digest in files.items():
        relative = Path(name)
        if relative.is_absolute() or '..' in relative.parts or sha(required(root, name)) != digest:
            raise ValueError('sealed original source changed: ' + name)
    revision = seal.get('native_revision', {})
    if (revision.get('construction_sha256') != sha(required(root, 'construction.json'))
            or revision.get('runner_sha256') != sha(required(root, 'runner.py'))):
        raise ValueError('sealed Native implementation changed')
    packet_path = required(root, 'reviewed-packet/reviewed-site.json')
    reviewed_site, _, _, _ = validate_packet(packet_path, case_id)
    site_path = required(root, 'site.json')
    site = json.loads(site_path.read_text(encoding='utf-8'))
    if site != reviewed_site:
        raise ValueError('original reviewed site differs')
    return site, {'site.json': sha(site_path), HISTORY: sha(required(root, HISTORY)),
                  'capture-seal.json': sha(seal_path)}


def diagnostic(root, case_id):
    note_path = required(root, 'diagnostic-source-note.json')
    note = json.loads(note_path.read_text(encoding='utf-8'))
    if (note.get('source_kind') != 'synthetic_diagnostic_fixture'
            or note.get('accepted_original_source') is not False
            or note.get('case_id') != case_id):
        raise ValueError('explicit synthetic flashing-red diagnostic provenance required')
    site_path = required(root, 'site.json')
    return json.loads(site_path.read_text(encoding='utf-8')), {
        'site.json': sha(site_path), HISTORY: sha(required(root, HISTORY)),
        'diagnostic-source-note.json': sha(note_path)}


def check_joins(root, history):
    cameras = rows(required(root, 'camera-frame-map.jsonl'))
    videos = rows(required(root, 'video_frames.jsonl'))
    if len(history) != FRAMES or len(cameras) != FRAMES or len(videos) != FRAMES:
        raise ValueError('full original flashing-red and camera history required')
    for index, (row, camera, video) in enumerate(zip(history, cameras, videos)):
        frame = row['frame']
        if (camera.get('frame_index') != index or camera.get('native_frame') != frame
                or camera.get('camera_frames') != {name: frame for name in CAMERAS}
                or video.get('video_frame') != index
                or video.get('carla_frame') != frame
                or video.get('native_frame', video.get('carla_frame')) != frame
                or abs(camera.get('time_s', -100) - row['time_s']) > 1e-5
                or abs(video.get('time_s', -100) - row['time_s']) > 1e-5):
            raise ValueError('original flashing-red/camera/native frame join changed')


def analyze(root):
    root = Path(root)
    config = json.loads(required(root, 'config.json').read_text(encoding='utf-8'))
    case_id = config.get('selected_case_id')
    matches = [case for case in CASES if case_id == ASSIGNMENT + '__' + case.suffix]
    if config.get('assignment_id') != ASSIGNMENT or len(matches) != 1:
        raise ValueError('saved exact flashing-red assignment differs')
    is_original = (root / 'capture-seal.json').is_file()
    site, source = original(root, case_id) if is_original else diagnostic(root, case_id)
    history = rows(required(root, HISTORY))
    check_joins(root, history)
    measured = measure_original(history, site, matches[0])
    description = config['case']['recording_description']
    channels = {
        'signal_flash': lambda row: row['red_lit'],
        'front_position': lambda row: row['front_m'],
        'complete_cessation': lambda row: row['speed_mps'] == 0,
        'stop_reference': lambda row: {'kind': matches[0].reference,
                                       'position_m': measured['surveyed_reference_m']},
        'occluder_source': lambda row: row['occluder_identity_sha256'],
        'camera_frame_identity': lambda row: row['frame'],
    }
    evidence = []
    for channel in description['channels']:
        name = channel['name']
        if name not in channels:
            raise ValueError('unknown flashing-red recording channel: ' + name)
        path = root / ('channel-' + name + '.jsonl')
        path.write_text(''.join(json.dumps({'time_s': row['time_s'],
                                            'value': channels[name](row)}) + '\n'
                                for row in history), encoding='utf-8')
        evidence.append({'name': name, 'unit': channel['unit'], 'reference': path.name})
    from worker_exchange.native_output import physical_result, write_result
    result = {'case_id': case_id,
        'measured_values': {'flashing_red_transitions': measured['flashing_red_transitions'],
                            'stopped_before_reference': any(row['before_reference']
                                                            for row in measured['stop_observations'])},
        'target_checks': [{'target': 'source-measured heavy-vehicle stop reference',
            'requested': matches[0].stop_offset_m,
            'measured': measured['stop_observations'][0]['front_m']
                        - measured['surveyed_reference_m'],
            'method': '900 sealed original motion/signal rows' if is_original
                      else '900 synthetic motion/signal rows',
            'tolerance': .25,
            'matched': False if is_original else abs(
                measured['stop_observations'][0]['front_m']
                - measured['surveyed_reference_m']
                - matches[0].stop_offset_m) <= .25,
            'physical_cause_confirmed': False,
            'cause_evidence': source}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False, 'termination_reason': 'saved measurement pending physical review',
        'physical_failure_flags': [] if is_original else ['original_signal_source_absent'],
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
        'measurements': {'flashing_red_heavy_vehicle_stop': {
            'method': 'measure_original', 'value': measured, 'sources': source}},
        'physical_checks': result['physical_checks'],
        'realized_observables': result['realized_observables'],
        'limitations': ['Original signal, occlusion, pixels and post-stop applicable rules require independent review.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior flashing-red analysis report')
    args.output.write_text(json.dumps(analyze(args.attempt), indent=2) + '\n',
                           encoding='utf-8')
