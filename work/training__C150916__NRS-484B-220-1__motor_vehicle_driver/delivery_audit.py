"""Audit exact saved one-way travel sources and synthetic physical diagnostic."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
VIDEOS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case, attempt, processing, physical, output):
    if not case.startswith(HERE.name + '__'):
        raise ValueError('Wrong exact delivery case')
    suffix = case[len(HERE.name) + 2:]
    if suffix not in ('designated', 'opposite'):
        raise ValueError('Unknown selected delivery case')
    pose, trace, frames = (rows(attempt / name) for name in
                           ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl'))
    if len(pose) != 600 or len(trace) != 600 or len(frames) != 600:
        raise ValueError('Incomplete original 600-frame source join')
    for index, (p, t, f) in enumerate(zip(pose, trace, frames)):
        if (p['native_frame'] != f['carla_frame'] or t['frame'] != f['carla_frame'] or
                f['video_frame'] != index or p['video_frame'] != index or
                abs(p['time_s'] - f['time_s']) > 1e-6 or
                abs(t['time_s'] - f['time_s']) > 1e-6 or
                p['requested_direction'] != suffix or
                set(p['camera_native_frames']) != set(VIDEOS) or
                any(p['camera_native_frames'][v] != f['carla_frame'] for v in VIDEOS)):
            raise ValueError('Original frame/time/camera join differs')
    receipt = json.loads(processing.read_text())
    if (receipt.get('case_id') != case or receipt.get('passed') is not True or
            receipt.get('recorded_only') is not True or
            receipt.get('originals_preserved') is not True or
            receipt.get('timestamp_joins', {}).get('frames') != 600):
        raise ValueError('Saved-only processing source proof incomplete')
    for name in ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl'):
        if sha(attempt / name) != receipt['original_source_hashes'].get(name):
            raise ValueError('Original source changed: ' + name)
    p = json.loads(physical.read_text())
    if (p.get('case_id') != case or p.get('kind') != 'complete_motion' or
            p.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met' or
            p.get('diagnostic_fixture') is not True or p.get('physical_or_legal_acceptance') is not False):
        raise ValueError('Independent diagnostic physical completion proof incomplete')
    pixels = {}
    for view in VIDEOS:
        name = view + '.mkv'
        video = attempt / name
        if not video.is_file() or sha(video) != receipt['original_source_hashes'].get(name):
            raise ValueError('Original camera source changed: ' + name)
        probe = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video),
                                '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                               capture_output=True, timeout=60, check=True)
        if not probe.stdout:
            raise ValueError('Camera pixel decode empty: ' + name)
        pixels[view] = hashlib.sha256(probe.stdout).hexdigest()
    report = {'format': 'nrs-484b-220-1-delivery-audit-v1', 'case_id': case,
              'candidate_id': receipt['candidate_id'], 'recorded_only': True,
              'frames': 600, 'source_hashes': {n: sha(attempt / n) for n in
              ('vehicle-pose.jsonl', 'trace.jsonl', 'video_frames.jsonl')},
              'decoded_first_frame_rgb_sha256': pixels,
              'physical_diagnostic_status': 'met', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'frames': 600, 'cameras': 4,
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--physical', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.case, args.attempt, args.processing, args.physical, args.output)
