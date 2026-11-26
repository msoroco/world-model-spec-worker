"""Independently audit saved railroad parking sources; diagnostic evidence stays diagnostic."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

from rail_proximity import measure

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
        raise ValueError('selected railroad parking case identity differs')
    source = required(attempt, 'original-rail-observations.json')
    receipt = json.loads(required(attempt, 'original-rail-receipt.json').read_text())
    packet = json.loads(source.read_text())
    if (receipt.get('case_id') != case_id or packet.get('case_id') != case_id
            or receipt.get('source_sha256') != sha(source)
            or receipt.get('diagnostic_fixture') is not diagnostic
            or packet.get('diagnostic_fixture', False) is not diagnostic
            or receipt.get('fps') != 20):
        raise ValueError('original railroad parking source receipt or provenance differs')
    measurement = measure(source)
    mapping = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    frames = packet['frames']
    if (len(frames) != receipt.get('frame_count') or len(mapping) != len(frames)
            or len(trace) != len(frames) or (not diagnostic and len(frames) != 900)):
        raise ValueError('original 900-frame ego and other-vehicle join differs')
    if not packet.get('site', {}).get('railroad_identity') or not packet['site'].get('carrier_provenance'):
        raise ValueError('reviewed original railroad carrier identity missing')
    if packet['site'].get('other_vehicle_actor_id') == packet.get('vehicle_actor_id'):
        raise ValueError('separate other vehicle identity missing')
    if frames[-1].get('vehicle_action') != 'park' or frames[-1].get('ego_speed_mps', 1) > .25:
        raise ValueError('original ego parked action not realized')
    from reviewed_site import nearest_distance
    actual = nearest_distance(frames[-1]['vehicle_footprint_m'], packet['rail_polylines_m'])
    if abs(actual - measurement['nearest_rail_distance_m']) > 1e-6:
        raise ValueError('final original footprint differs from measured rail distance')
    for index, (frame, mapped, native) in enumerate(zip(frames, mapping, trace)):
        if (mapped.get('video_frame') != index or mapped.get('carla_frame') != frame.get('frame')
                or mapped.get('native_frame') != frame.get('frame')
                or native.get('frame') != frame.get('frame')
                or abs(mapped.get('time_s', -1) - frame['time_s']) > 1e-4
                or abs(native.get('time_s', -1) - frame['time_s']) > 1e-4):
            raise ValueError('original frame/time join differs')
        if frame.get('other_vehicle_actor_id') != packet['site']['other_vehicle_actor_id']:
            raise ValueError('other vehicle identity changed')
        if not isinstance(frame.get('ego_xyz_m'), list) or not isinstance(frame.get('other_vehicle_xyz_m'), list):
            raise ValueError('original ego or other vehicle trajectory missing')
        nearest_distance(frame.get('vehicle_footprint_m'), packet['rail_polylines_m'])
        expected = 'synthetic_diagnostic' if diagnostic else 'original_native_snapshot'
        if frame.get('observation_source') != expected:
            raise ValueError('original snapshot observation source differs')
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
    return {'format': 'worker-independent-rail-delivery', 'case_id': case_id,
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
