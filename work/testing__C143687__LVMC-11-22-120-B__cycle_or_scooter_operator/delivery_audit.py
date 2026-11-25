"""Independent source-gated audit for released original bicycle attempts."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from native_measurement import measure
from reviewed_site import verify

ASSIGNMENT = 'testing__C143687__LVMC-11-22-120-B__cycle_or_scooter_operator'
MOTIONS = {'posted_enter': 'enter_roadway', 'posted_stop': 'stop_before_roadway',
           'posted_remain_trail': 'remain_trail'}
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
    if (path.is_symlink() or not path.is_file() or
            not path.resolve().is_relative_to(root) or sha(path) != ref['sha256']):
        raise ValueError('sealed original source changed: ' + str(rel))
    return path


def probe_video(path: Path) -> dict:
    completed = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries',
                                'stream=nb_read_frames,r_frame_rate,width,height',
                                '-of', 'json', str(path)], capture_output=True,
                               text=True, check=True, timeout=120)
    streams = json.loads(completed.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('one original video stream required')
    return streams[0]


def audit(root: Path, receipt: dict, probe=probe_video) -> dict:
    root = Path(root).resolve()
    case_id = receipt.get('case_id', '')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if case_id != ASSIGNMENT + '__' + suffix or suffix not in MOTIONS:
        raise ValueError('exact selected bicycle case required')
    if (receipt.get('source_kind') != 'original_native_attempt' or
            receipt.get('diagnostic_fixture') is True or
            receipt.get('native_process_exit_code') != 0 or
            receipt.get('owner_released') is not True or
            not receipt.get('attempt_id') or not receipt.get('recording_id')):
        raise ValueError('successful released original Native attempt required')
    site_path = linked(root, receipt.get('site_ref'))
    reviewed = verify(site_path)
    seal_path = linked(root, receipt.get('capture_seal_ref'))
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if (seal.get('source_kind') != 'original_native_capture_seal' or
            seal.get('case_id') != case_id or
            seal.get('attempt_id') != receipt['attempt_id'] or
            seal.get('recording_id') != receipt['recording_id']):
        raise ValueError('sealed original Native identity differs')
    videos = receipt.get('video_refs')
    if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
        raise ValueError('four original camera videos required')
    refs = [receipt.get('site_ref'), receipt.get('capture_packet_ref'),
            receipt.get('frame_map_ref'), receipt.get('trace_ref'), *videos.values()]
    for ref in refs:
        if not isinstance(ref, dict) or seal.get('sources', {}).get(ref.get('path')) != ref.get('sha256'):
            raise ValueError('sealed original source inventory differs')
    frame_path = linked(root, receipt.get('frame_map_ref'))
    frame_map = json.loads(frame_path.read_text(encoding='utf-8'))
    frames = frame_map.get('frames')
    if (frame_map.get('source_kind') != 'original_native_frame_map' or
            frame_map.get('case_id') != case_id or not isinstance(frames, list) or len(frames) != 900):
        raise ValueError('complete original 900-frame map required')
    native = [row.get('native_frame') for row in frames]
    if any(type(v) is not int for v in native) or any(b <= a for a, b in zip(native, native[1:])):
        raise ValueError('original Native frame IDs not increasing')
    for i, row in enumerate(frames):
        if (row.get('frame') != i or row.get('time_s') != i / 20 or
                set(row.get('camera_frames', {})) != set(CAMERAS) or
                any(row['camera_frames'][name] != native[i] for name in CAMERAS)):
            raise ValueError('original four-camera time join missing')
    video_hashes = {}
    for name in CAMERAS:
        path = linked(root, videos[name])
        stream = probe(path)
        if stream.get('nb_read_frames') != '900' or stream.get('r_frame_rate') != '20/1':
            raise ValueError('original camera full decode failed: ' + name)
        if int(stream.get('width', 0)) < 640 or int(stream.get('height', 0)) < 360:
            raise ValueError('original camera resolution below review floor')
        video_hashes[name] = sha(path)
    packet_path = linked(root, receipt.get('capture_packet_ref'))
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if packet.get('source_kind') != 'original_native_capture' or any(
            row.get('diagnostic_fixture') is True for row in packet.get('frames', [])):
        raise ValueError('diagnostic motion cannot be original delivery')
    measured = measure(reviewed['site'], packet, {'case_id': case_id, 'motion': MOTIONS[suffix]})
    trace_path = linked(root, receipt.get('trace_ref'))
    trace = [json.loads(line) for line in trace_path.read_text(encoding='utf-8').splitlines()]
    if len(trace) != 900 or any(row.get('diagnostic_fixture') is True for row in trace):
        raise ValueError('original trace incomplete or diagnostic')
    if any(row.get('frame') != frame['native_frame'] or row.get('time_s') != i / 20
           for i, (row, frame) in enumerate(zip(trace, frames))):
        raise ValueError('original trace/frame-map join differs')
    return {'format': 'c143687-original-attempt-audit-v1', 'case_id': case_id,
            'attempt_id': receipt['attempt_id'], 'recording_id': receipt['recording_id'],
            'source_kind': 'original_native_attempt', 'site_sha256': sha(site_path),
            'capture_seal_sha256': sha(seal_path), 'capture_packet_sha256': sha(packet_path),
            'frame_map_sha256': sha(frame_path), 'trace_sha256': sha(trace_path),
            'video_sha256': video_hashes, 'frames_checked': 900,
            'roadway_frames': measured['roadway_frames'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'original_bicycle_segment_readback'],
            'physical_completion': 'requires independent local visual and motion review',
            'legal_judgment': 'unresolved'}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--authority-root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.authority_root.resolve()):
        raise ValueError('fresh audit output outside original source root required')
    result = audit(args.authority_root, json.loads(args.receipt.read_text(encoding='utf-8')))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
