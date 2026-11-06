"""Finalize saved bicycle/motorist evidence without making a legal finding."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from measure import measure


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decoded_frames(path: Path) -> int:
    result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames', '-of', 'default=noprint_wrappers=1:nokey=1',
        str(path)], text=True, capture_output=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source video decode failed: ' + path.name)
    return int(result.stdout.strip())


def finalize(attempt: Path, output: Path) -> dict:
    attempt = attempt.resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Use a fresh saved attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('law_id') != 'NRS-484B-270-7a' or config.get('cell_id') != 'C111294':
        raise ValueError('Frozen case identity differs')
    manifest = json.loads(required(attempt, 'capture/manifest.json').read_text())
    source = required(attempt, 'interaction.json')
    expected = manifest.get('sources', {}).get('interaction.json')
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError('Original interaction source hash absent')
    value = measure(source, expected, required(attempt, 'road.xodr'))
    if value['case'] != config['case_suffix'] or config['case_id'].split('__')[-1] != value['case']:
        raise ValueError('Case source differs')
    count = config['rate_hz'] * config['duration_s']
    if count != 480 or manifest.get('frames') != count or manifest.get('extraction_confirmed') is not True:
        raise ValueError('Full saved extraction absent')
    joined = {name: rows(required(attempt, name)) for name in
              ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl', 'native_samples.jsonl')}
    if any(len(group) != count for group in joined.values()):
        raise ValueError('Saved frame count differs')
    interaction = json.loads(source.read_text())['frames']
    previous_frame = None
    first_time = joined['video_frames.jsonl'][0].get('time_s')
    if type(first_time) not in (int, float) or not math.isfinite(first_time):
        raise ValueError('Original first timestamp absent')
    source_kind = json.loads(source.read_text())['source_kind']
    for index, (trace, evidence, mapping, native, row) in enumerate(zip(
            joined['trace.jsonl'], joined['capture/evidence.jsonl'],
            joined['video_frames.jsonl'], joined['native_samples.jsonl'], interaction)):
        frame = mapping.get('native_frame')
        time = first_time + index / 20
        if type(frame) is not int or (previous_frame is not None and frame <= previous_frame):
            raise ValueError('Original Native frame order differs')
        previous_frame = frame
        if (mapping.get('video_frame'), mapping.get('native_frame'), mapping.get('carla_frame')) != (index, frame, frame):
            raise ValueError('Original frame mapping differs')
        if source_kind in ('synthetic_original_shape_emulation','original_native_and_video') and row.get('native_frame') != frame:
            raise ValueError('Original interaction frame differs')
        if any(item != frame for item in (trace.get('frame'), evidence.get('original_frame'), native.get('native_frame'))):
            raise ValueError('Original Native frame join differs')
        if any(type(item) not in (int, float) or not math.isclose(item, time, abs_tol=1e-4) for item in
               (mapping.get('time_s'), trace.get('time_s'), evidence.get('recording_time_s'), native.get('time_s'))):
            raise ValueError('Original Native timestamp join differs')
        if native.get('bicycle') != row['bicycle'] or native.get('motor_vehicle') != row['motor_vehicle']:
            raise ValueError('Original bicycle/motorist actor join differs')
        if any(abs(a-b)>1e-4 for a,b in zip(trace.get('position_m', [])[:2], row['bicycle']['center_xy_m'])) or len(trace.get('position_m',[]))<2:
            raise ValueError('Bicycle trace position differs')
        if evidence.get('ego', {}).get('body_vertices_m') != native.get('bicycle_body_vertices_m'):
            raise ValueError('Original bicycle body source differs')
    videos = [name + '.mkv' for name in
              ('overview', 'bicycle_approach', 'motorist_approach', 'conflict')]
    counts = {name: decoded_frames(required(attempt, name)) for name in videos}
    if any(frames != count for frames in counts.values()):
        raise ValueError('Original video frame count differs')
    recording = []
    for channel in config['recording_description']['channels']:
        name = channel['name']
        path = 'channels/' + name + '.jsonl'
        if len(rows(required(attempt, path))) != count:
            raise ValueError('Channel frame count differs: ' + name)
        recording.append({'name': name, 'unit': channel['unit'], 'reference': path})
    expected_brake = value['case'] == 'witness_2'
    observed_brake = value['motorist_braked']
    result = {'case_id': config['case_id'],
        'measured_values': {'bicycle_motorist_interaction': value},
        'target_checks': [{'target': 'motorist_braked', 'requested': expected_brake,
            'measured': observed_brake, 'method': 'saved source-hashed bicycle/motorist full-body frame join',
            'tolerance': 0, 'matched': observed_brake == expected_brake,
            'physical_cause_confirmed': False,
            'cause_evidence': ['interaction.json', 'native_samples.jsonl']}],
        'setup_confirmed': True, 'behavior_attempted': True,
        'maneuver_completed': True, 'termination_reason': 'full saved diagnostic duration',
        'physical_failure_flags': ['human_propulsion_intent_and_original_pixels_unverified'],
        'trace_reference': 'trace.jsonl', 'video_references': videos,
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': config['recording_description'],
        'recording_evidence': recording,
        'realized_observables': {'motor_braking_frames': {'value': value['motor_braking_frames'],
            'unit': 'frame', 'method': 'source-hashed motor-vehicle brake samples',
            'time_window': 'saved 24 s diagnostic', 'statistic': 'count',
            'reference': 'interaction.json'}},
        'provenance_kind': 'synthetic_cpu' if not value['physical_behavior_observed'] else 'native',
        'accepted': False, 'legal_verdict_claimed': False}
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111294-saved-analysis-v1', 'case_id': config['case_id'],
        'candidate_id': config['candidate_id'],
        'measurements': {'bicycle_motorist_interaction': {'method': 'measure', 'value': value,
            'sources': {'interaction.json': sha(source), 'road.xodr': sha(attempt / 'road.xodr')}}},
        'original_joins': {name: sha(required(attempt, name)) for name in joined},
        'video_frames': counts,
        'scope': 'synthetic saved diagnostic or source-bound original capture; no acceptance or legal verdict'}
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (attempt / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output)))
