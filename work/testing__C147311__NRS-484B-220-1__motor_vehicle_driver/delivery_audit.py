"""Independent original-attempt one-way sign and travel audit."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from one_way_direction import CASES
from reviewed_source import measure_reviewed, verify

ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def linked(root: Path, ref: dict) -> Path:
    if not isinstance(ref, dict) or not isinstance(ref.get('path'), str) or not ref.get('sha256'):
        raise ValueError('sealed original source reference required')
    rel = Path(ref['path'])
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('original source path invalid')
    path = root / rel
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root) or sha(path) != ref['sha256']:
        raise ValueError('sealed original source changed: ' + str(rel))
    return path


def probe_video(path: Path) -> dict:
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                             '-count_frames', '-show_entries',
                             'stream=nb_read_frames,r_frame_rate,width,height',
                             '-of', 'json', str(path)], capture_output=True,
                            text=True, check=True, timeout=120)
    streams = json.loads(result.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('one original video stream required')
    subprocess.run(['ffmpeg', '-v', 'error', '-xerror', '-i', str(path),
                    '-f', 'null', '-'], capture_output=True, check=True, timeout=180)
    return streams[0]


def audit(root: Path, receipt: dict, probe=probe_video) -> dict:
    root = Path(root).resolve()
    case_id = receipt.get('case_id', '')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id != ASSIGNMENT + '__' + suffix or suffix not in {c.name for c in CASES}:
        raise ValueError('exact selected one-way case required')
    if (receipt.get('source_kind') != 'original_native_attempt' or
            receipt.get('diagnostic_fixture') is True or
            receipt.get('native_process_exit_code') != 0 or
            receipt.get('owner_released') is not True or
            not receipt.get('attempt_id') or not receipt.get('recording_id')):
        raise ValueError('successful released original Native attempt required')
    site = linked(root, receipt.get('site_ref'))
    reviewed = verify(site, suffix)
    seal_path = linked(root, receipt.get('capture_seal_ref'))
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if (seal.get('source_kind') != 'original_native_capture_seal' or
            seal.get('case_id') != case_id or
            seal.get('attempt_id') != receipt['attempt_id'] or
            seal.get('recording_id') != receipt['recording_id']):
        raise ValueError('sealed original Native identity differs')
    refs = [receipt.get('site_ref'), receipt.get('frame_map_ref'),
            receipt.get('trace_ref')] + list(receipt.get('video_refs', {}).values())
    for ref in refs:
        if not isinstance(ref, dict) or seal.get('sources', {}).get(ref.get('path')) != ref.get('sha256'):
            raise ValueError('sealed original source inventory differs')
    frame_path = linked(root, receipt.get('frame_map_ref'))
    frame_map = json.loads(frame_path.read_text(encoding='utf-8'))
    frames = frame_map.get('frames')
    if (frame_map.get('source_kind') != 'original_native_frame_map' or
            frame_map.get('case_id') != case_id or not isinstance(frames, list) or
            len(frames) != 900):
        raise ValueError('complete original 900-frame map required')
    native = [row.get('native_frame') for row in frames]
    if any(type(value) is not int for value in native) or any(b <= a for a, b in zip(native, native[1:])):
        raise ValueError('original Native frame IDs not increasing')
    for i, row in enumerate(frames):
        if row.get('frame') != i or row.get('time_s') != i / 20 or set(row.get('camera_frames', {})) != set(CAMERAS):
            raise ValueError('original four-camera time join missing')
        if any(row['camera_frames'][name] != native[i] for name in CAMERAS):
            raise ValueError('original camera Native frame differs')
    videos = receipt.get('video_refs')
    if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
        raise ValueError('four original camera videos required')
    video_hashes = {}
    for name in CAMERAS:
        path = linked(root, videos[name])
        stream = probe(path)
        if stream.get('nb_read_frames') != '900' or stream.get('r_frame_rate') != '20/1':
            raise ValueError('original camera full decode failed: ' + name)
        expected_size = (1920, 1080) if name == 'overview' else (1280, 720)
        if (stream.get('width'), stream.get('height')) != expected_size:
            raise ValueError('original camera size differs from capture profile: ' + name)
        video_hashes[name] = sha(path)
    trace_path = linked(root, receipt.get('trace_ref'))
    rows = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines()]
    if any(row.get('diagnostic_fixture') is True for row in rows):
        raise ValueError('diagnostic motion cannot be original delivery')
    measured = measure_reviewed(rows, site, suffix)
    if len(rows) != 900 or measured['actual_direction'] != reviewed['scene']['direction']:
        raise ValueError('actual original travel direction differs')
    return {'format': 'c147311-original-attempt-audit-v1',
            'case_id': case_id, 'attempt_id': receipt['attempt_id'],
            'recording_id': receipt['recording_id'],
            'source_kind': 'original_native_attempt',
            'site_sha256': sha(site), 'capture_seal_sha256': sha(seal_path),
            'frame_map_sha256': sha(frame_path), 'trace_sha256': sha(trace_path),
            'video_sha256': video_hashes, 'frames_checked': 900,
            'actual_direction': measured['actual_direction'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels',
                       'original_sign_and_velocity_readback'],
            'physical_completion': 'requires independent local visual and motion review',
            'legal_judgment': 'unresolved'}


def main() -> None:
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--authority-root', type=Path, required=True)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.authority_root.resolve()):
        raise ValueError('fresh audit output outside original source root required')
    result = audit(args.authority_root, json.loads(args.receipt.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
