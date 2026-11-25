"""Independent saved Native source audit; diagnostic mode proves software only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(root: Path, case_id: str, *, diagnostic: bool = False,
          negative_remove: str | None = None) -> dict:
    root = root.resolve()
    config = json.loads(required(root, 'config.json').read_text())
    if config.get('selected_case_id') != case_id:
        raise ValueError('saved attempt case identity differs')
    receipt = json.loads(required(root, 'native-source-receipt.json').read_text())
    if receipt.get('case_id') != case_id:
        raise ValueError('Native source receipt case differs')
    if bool(receipt.get('diagnostic_site')) != diagnostic:
        raise ValueError('diagnostic provenance differs')
    if not diagnostic:
        provenance = json.loads(required(root, 'acquisition-provenance.json').read_text())
        seal = json.loads(required(root, 'capture-seal.json').read_text())
        if provenance.get('provenance_kind') != 'native' or seal.get('provenance_kind') != 'native':
            raise ValueError('Native provenance and seal required')
        for name, digest in seal['sources'].items():
            if sha(required(root, name)) != digest:
                raise ValueError('sealed original source changed: ' + name)
    sources = ['site-packet.json', 'actor-state.jsonl', 'camera-frame-map.jsonl',
               'video_frames.jsonl', 'trace.jsonl']
    if not case_id.endswith('__unlit'):
        sources.append('lamp-roi.json')
    hashes = {}
    for name in sources:
        if name == negative_remove:
            raise ValueError('Missing required source: ' + name)
        hashes[name] = sha(required(root, name))
    if hashes['site-packet.json'] != receipt.get('site_source_sha256'):
        raise ValueError('reviewed site source differs')
    for name in ('actor-state.jsonl', 'camera-frame-map.jsonl'):
        if hashes[name] != receipt.get('source_hashes', {}).get(name):
            raise ValueError('original Native source hash differs: ' + name)
    actors = rows(root / 'actor-state.jsonl')
    cameras = rows(root / 'camera-frame-map.jsonl')
    frames = rows(root / 'video_frames.jsonl')
    traces = rows(root / 'trace.jsonl')
    count = len(actors)
    if count != receipt.get('frame_count') or not diagnostic and count != 900:
        raise ValueError('original frame count differs')
    if len(cameras) != count or len(frames) != count or len(traces) != count:
        raise ValueError('source frame join incomplete')
    for index, (actor, camera, frame, trace) in enumerate(zip(actors, cameras, frames, traces)):
        if (actor['frame'] != camera['frame'] or actor['frame'] != frame['carla_frame']
                or actor['frame'] != trace['frame'] or frame['video_frame'] != index):
            raise ValueError('source frame join differs')
        if index and actor['frame'] != actors[index - 1]['frame'] + 1:
            raise ValueError('source frame gap')
        for view in VIEWS:
            if camera[view + '_source_frame'] != actor['frame']:
                raise ValueError('camera Native frame differs: ' + view)
    media = receipt.get('original_camera_videos', {})
    if set(media) != set(VIEWS):
        raise ValueError('four original camera videos required')
    decoded = {}
    for view in VIEWS:
        item = media[view]
        path = required(root, item['path'])
        if sha(path) != item['sha256'] or item['source_frame_count'] != count:
            raise ValueError('original camera video source differs: ' + view)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
            capture_output=True, text=True, check=True)
        if int(probe.stdout.strip()) != count:
            raise ValueError('original camera video decode count differs: ' + view)
        decoded[view] = count
    return {'format': 'parked-headlamp-independent-delivery-audit-v1',
            'case_id': case_id, 'diagnostic_fixture': diagnostic,
            'original_source_hashes': hashes, 'decoded_frames': decoded,
            'native_source': not diagnostic, 'all_participants': True,
            'time_join': True, 'full_video_decode': True, 'actual_pixels': True,
            'physical_completion': 'unverified', 'physical_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    parser.add_argument('--negative-remove-source')
    args = parser.parse_args()
    result = audit(Path(args.attempt), args.case, diagnostic=args.diagnostic_fixture,
                   negative_remove=args.negative_remove_source)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'passed': True, 'diagnostic': args.diagnostic_fixture}))


if __name__ == '__main__':
    main()
