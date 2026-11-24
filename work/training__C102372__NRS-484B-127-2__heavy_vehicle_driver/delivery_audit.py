"""Audit exact selected recorded sources before local GPU delivery."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


HERE = Path(__file__).resolve().parent
VIDEOS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
ROWS = ('native_samples.jsonl', 'trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(path: Path) -> Path:
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    return path


def records(path: Path) -> list:
    return [json.loads(line) for line in require(path).read_text().splitlines()]


def audit(case: str, attempt: Path, processing: Path, output: Path) -> None:
    if not case.startswith(HERE.name + '__'):
        raise ValueError('Wrong exact delivery case')
    suffix = case.rsplit('__', 1)[1]
    if suffix not in ('probe_1', 'probe_2', 'two_lane_exception', 'passing_hold',
                      'passing_overtake', 'conditions_steady', 'conditions_lead_brake'):
        raise ValueError('Unknown selected delivery case')
    source = {name: records(attempt / name) for name in ROWS}
    if any(len(rows) != 600 for rows in source.values()):
        raise ValueError('Incomplete original 600-frame source join')
    for index, (native, trace, evidence, frame) in enumerate(zip(*(source[n] for n in ROWS))):
        carla_frame = frame.get('carla_frame')
        if (native.get('native_frame'), frame.get('native_frame'), frame.get('video_frame'),
                native.get('carla_frame'), trace.get('frame'), evidence.get('original_frame')) != (
                index, index, index, carla_frame, carla_frame, carla_frame):
            raise ValueError('Original frame/time join differs')
        ego, lead = native.get('ego', {}), native.get('lead', {})
        for actor in (ego, lead):
            if (actor.get('actor_class') != 'truck_or_combination' or
                    len(actor.get('body_vertices_m', [])) != 8 or
                    actor.get('body_width_m', 0) < 80 * 0.0254):
                raise ValueError('Original qualifying participant missing')
    receipt = json.loads(require(processing).read_text())
    if (receipt.get('case_id'), receipt.get('passed'), receipt.get('recorded_only'),
            receipt.get('originals_preserved'), receipt.get('timestamp_joins', {}).get('frames')) != (
            case, True, True, True, 600):
        raise ValueError('Saved processing source proof incomplete')
    result = json.loads(require(Path(receipt['result'])).read_text())
    if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
        raise ValueError('Source-bound physical completion not met')
    if result.get('physical_acceptance_claimed') is not False:
        raise ValueError('Diagnostic fixture claimed physical acceptance')
    pixels = {}
    for name in VIDEOS:
        video = require(attempt / name)
        if sha(video) != receipt['original_source_hashes'].get(name):
            raise ValueError('Original camera source changed')
        probe = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-frames:v', '1',
                                '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                               capture_output=True, timeout=60, check=True)
        if not probe.stdout:
            raise ValueError('Camera pixel decode empty: ' + name)
        pixels[name] = hashlib.sha256(probe.stdout).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    report = {'format': 'c102372-selected-delivery-audit-v1', 'case_id': case,
              'candidate_id': receipt['candidate_id'], 'recorded_only': True,
              'frames': 600, 'source_hashes': {name: sha(attempt / name) for name in ROWS},
              'decoded_first_frame_rgb_sha256': pixels,
              'physical_maneuver_status': 'met', 'diagnostic_fixture': True,
              'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'case_id': case, 'frames': 600, 'cameras': 4,
                      'diagnostic_fixture': True}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    audit(args.case, args.attempt, args.processing, args.output)
