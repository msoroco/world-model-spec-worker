"""Independently audit saved WALK sources; diagnostic evidence stays diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from walk_signal_measurement import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
DIMS = {'overview': (1920, 1080), 'approach': (1280, 720),
        'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(attempt: Path, case_id: str, diagnostic: bool = False) -> dict:
    attempt = attempt.resolve()
    config = json.loads(required(attempt, 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('selected WALK case identity differs')
    source = required(attempt, 'original-walk-observations.json')
    receipt = json.loads(required(attempt, 'original-walk-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (receipt.get('case_id') != case_id or packet.get('case_id') != case_id
            or receipt.get('source_sha256') != sha(source)
            or receipt.get('diagnostic_fixture') is not diagnostic
            or packet.get('diagnostic_fixture', False) is not diagnostic
            or receipt.get('fps') != 20):
        raise ValueError('original WALK source receipt or provenance differs')
    measurement = measure(source)
    mapping = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    frames = packet['frames']
    if (len(frames) != receipt.get('frame_count') or len(mapping) != len(frames)
            or len(trace) != len(frames) or (not diagnostic and len(frames) != 900)):
        raise ValueError('original 900-frame signal, walker and driver join differs')
    for index, (frame, mapped, native) in enumerate(zip(frames, mapping, trace)):
        if (mapped.get('video_frame') != index or mapped.get('carla_frame') != frame.get('frame')
                or mapped.get('native_frame') != frame.get('frame')
                or native.get('frame') != frame.get('frame')
                or abs(mapped.get('time_s', -1) - frame['time_s']) > 1e-4
                or abs(native.get('time_s', -1) - frame['time_s']) > 1e-4):
            raise ValueError('original frame/time join differs')
        if not frame.get('driver_actor_ids') or not isinstance(frame.get('exception_context'), dict):
            raise ValueError('driver or statutory context missing')
    media = {}
    for camera in CAMERAS:
        path = required(attempt, camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-count_frames', '-show_entries',
            'stream=nb_read_frames,codec_name,width,height,r_frame_rate,avg_frame_rate',
            '-of', 'json', str(path)], capture_output=True, text=True, timeout=60)
        if probe.returncode:
            raise ValueError('four-camera ffprobe failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1 or int(streams[0]['nb_read_frames']) != len(frames):
            raise ValueError('four-camera frame count differs: ' + camera)
        stream = streams[0]
        if not diagnostic and (stream.get('codec_name') != 'ffv1'
                or (stream.get('width'), stream.get('height')) != DIMS[camera]
                or stream.get('r_frame_rate') != '20/1'):
            raise ValueError('original video codec, size or rate differs: ' + camera)
        decoded = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error',
            '-nostdin', '-i', str(path), '-f', 'null', '-'],
            capture_output=True, timeout=120)
        if decoded.returncode:
            raise ValueError('four-camera full decode failed: ' + camera)
        media[camera] = {'sha256': sha(path), 'frames': len(frames),
            'codec': stream.get('codec_name'), 'width': stream.get('width'),
            'height': stream.get('height')}
    return {'format': 'worker-independent-walk-delivery', 'case_id': case_id,
        'passed': True, 'diagnostic_only': diagnostic, 'physical_acceptance': False,
        'legal_acceptance': False, 'frame_count': len(frames),
        'source_sha256': sha(source), 'measurement': measurement,
        'full_video_decode': media}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.attempt, args.case_id, args.diagnostic)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case_id, 'passed': True}))


if __name__ == '__main__':
    main()
