"""Independent original-source audit for one saved C111329 attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import audit as audit_delivery
from reviewed_site import verify as verify_site
from saved_process import ASSIGNMENT, CASES, _read
from saved_media_audit import PROFILE_DIMENSIONS

CAMERAS = tuple(PROFILE_DIMENSIONS)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path, count: int) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]
    if len(rows) != count:
        raise ValueError('original trace or frame map count differs from 900-frame profile')
    return rows


def audit(attempt: Path, case_id: str, refs: list[dict], *,
          allow_diagnostic: bool = False, expected_frames: int = 900) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    if not allow_diagnostic and expected_frames != 900:
        raise ValueError('production requires pinned 900-frame original profile')
    if len(refs) != 4 or not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('four original source references and exact case required')
    suffix = case_id.removeprefix(ASSIGNMENT + '__')
    if suffix not in CASES:
        raise ValueError('unknown exact C111329 case')
    site, native = _read(attempt, refs[0]), _read(attempt, refs[1])
    if not allow_diagnostic:
        if site.get('diagnostic') is not False:
            raise ValueError('unreviewed original site rejected')
        verify_site(attempt, site, *CASES[suffix])
    receipt = audit_delivery(attempt, case_id, *refs,
                             expected_frames=expected_frames,
                             allow_diagnostic=allow_diagnostic)
    seal_path = attempt / 'capture-seal.json'
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    if seal.get('format') != 'worker-sealed-capture' or seal.get('frames') != expected_frames:
        raise ValueError('original capture seal or frame count mismatch')
    if not allow_diagnostic and seal.get('diagnostic_fixture') is not False:
        raise ValueError('diagnostic capture seal rejected')
    if seal.get('restoration', {}).get('restored') is not True:
        raise ValueError('Native world restoration unverified')
    sources = seal.get('sources')
    if not isinstance(sources, dict):
        raise ValueError('original capture source seal absent')
    required = ('road.xodr', 'trace.jsonl', 'video_frames.jsonl',
                'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                *(camera + '.mkv' for camera in CAMERAS))
    for rel in required:
        path = (attempt / rel).resolve(strict=True)
        if not path.is_relative_to(attempt) or sources.get(rel) != _sha(path):
            raise ValueError('sealed original missing or changed: ' + rel)
    if site.get('map_sha256') != _sha(attempt / 'road.xodr'):
        raise ValueError('original OpenDRIVE differs from surveyed site')
    capture_manifest = json.loads((attempt / 'capture/manifest.json').read_text(encoding='utf-8'))
    if (capture_manifest.get('case_id') != case_id or
            capture_manifest.get('frames') != expected_frames or
            (not allow_diagnostic and capture_manifest.get('diagnostic_fixture') is not False)):
        raise ValueError('original capture manifest identity or frame count mismatch')
    rows = native['rows']
    mapped = _jsonl(attempt / 'video_frames.jsonl', expected_frames)
    trace = _jsonl(attempt / 'trace.jsonl', expected_frames)
    evidence = _jsonl(attempt / 'capture/evidence.jsonl', expected_frames)
    graphs = _jsonl(attempt / 'capture/native/frames.jsonl', expected_frames)
    for i, row in enumerate(rows):
        frame, time = row['original_frame'], row['elapsed_seconds']
        if (mapped[i].get('video_frame') != i or mapped[i].get('carla_frame') != frame or
                mapped[i].get('native_frame') != frame or
                trace[i].get('frame') != frame or evidence[i].get('original_frame') != frame or
                graphs[i].get('frame') != frame or
                any(abs(float(item.get(key, -1)) - time) > .002 for item, key in
                    ((mapped[i], 'time_s'), (trace[i], 'time_s'),
                     (evidence[i], 'recording_time_s'), (graphs[i], 'simulation_time')))):
            raise ValueError('original 900-frame map, trace and evidence join mismatch')
    video = {}
    for camera in CAMERAS:
        path = attempt / (camera + '.mkv')
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                                '-count_frames', '-show_entries',
                                'stream=codec_name,width,height,r_frame_rate,nb_read_frames',
                                '-of', 'json', str(path)], capture_output=True, text=True)
        if probe.returncode:
            raise ValueError('original video full decode failed: ' + camera)
        streams = json.loads(probe.stdout).get('streams', [])
        if len(streams) != 1:
            raise ValueError('original video stream missing: ' + camera)
        stream = streams[0]
        dimensions = [stream.get('width'), stream.get('height')]
        if (stream.get('codec_name') != 'ffv1' or stream.get('r_frame_rate') != '20/1' or
                int(stream.get('nb_read_frames', -1)) != expected_frames or
                (not allow_diagnostic and dimensions != PROFILE_DIMENSIONS[camera])):
            raise ValueError('original video codec, rate, dimensions or frame count mismatch: ' + camera)
        video[camera] = {'sha256': sources[camera + '.mkv'], 'decoded_frames': expected_frames,
                         'dimensions': dimensions, 'codec': 'ffv1', 'fps': 20}
    return {**receipt, 'format': 'c111329-original-attempt-audit-v1',
            'capture_seal_sha256': _sha(seal_path), 'video': video,
            'source_join_count': expected_frames, 'production': not allow_diagnostic}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--refs', type=Path, required=True,
                        help='JSON array of site, Native, camera, saved receipt path/hash references')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    parser.add_argument('--expected-frames', type=int, default=900)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('original audit output already exists')
    refs = json.loads(args.refs.read_text(encoding='utf-8'))
    result = audit(args.attempt, args.case, refs,
                   allow_diagnostic=args.allow_diagnostic,
                   expected_frames=args.expected_frames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
