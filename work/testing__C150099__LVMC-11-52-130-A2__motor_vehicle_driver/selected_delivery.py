"""Read-only selected delivery audit; diagnostic inputs never become original claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import audit_saved_channels

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(path: Path, expected: int) -> dict:
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries',
                            'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                           text=True, capture_output=True, check=True)
    streams = json.loads(probe.stdout)['streams']
    if len(streams) != 1 or int(streams[0]['nb_read_frames']) != expected:
        raise ValueError('full video frame count differs: ' + path.name)
    if int(streams[0]['width']) < 16 or int(streams[0]['height']) < 16:
        raise ValueError('video pixel plane missing: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                              '-map', '0:v:0', '-f', 'framemd5', '-'],
                             text=True, capture_output=True, check=True)
    frame_rows = [row for row in decoded.stdout.splitlines() if row and not row.startswith('#')]
    if len(frame_rows) != expected or any(len(row.split(',')) < 6 for row in frame_rows):
        raise ValueError('decoded pixel frame inventory differs: ' + path.name)
    return {'sha256': sha(path), 'frames': len(frame_rows),
            'pixel_digest_sha256': hashlib.sha256(decoded.stdout.encode()).hexdigest()}


def audit(attempt: Path, case: str, allow_diagnostic: bool) -> dict:
    channels = audit_saved_channels(attempt, case, allow_diagnostic=allow_diagnostic)
    original = attempt / 'original-attempt'
    inventory = json.loads((original / 'inventory.json').read_text())
    rows = [json.loads(row) for row in (original / 'history.jsonl').read_text().splitlines()]
    if not rows or any(row.get('case_id') != case or not row.get('ego_id') or
                       not row.get('sign_id') for row in rows):
        raise ValueError('selected participants missing from original history')
    if any(row['ego_id'] != rows[0]['ego_id'] or row['sign_id'] != rows[0]['sign_id']
           for row in rows):
        raise ValueError('selected participant identity changes')
    source = original / 'source-review'
    required = ('map', 'jurisdiction', 'fire_code_designation', 'posting_authority',
                'posted_extent', 'sign_identity', 'sign_appearance', 'curb_geometry',
                'property_source', 'route', 'camera_plan')
    if any(not (source / (name + '.txt')).is_file() for name in required):
        raise ValueError('selected Native source review incomplete')
    if inventory.get('diagnostic_fixture') is not True:
        if len(rows) != 900 or not (original / 'reviewed-packet.json').is_file():
            raise ValueError('original Native acquisition sources incomplete')
    media = {name: decode(attempt / (name + '.mkv'), len(rows)) for name in CAMERAS}
    raw = decode(attempt / 'raw.mkv', len(rows))
    return {'format': 'worker-selected-fire-lane-delivery-audit', 'case_id': case,
            'checks_executed': ['native_source', 'all_participants', 'time_join',
                                'full_video_decode', 'actual_pixels', 'physical_completion'],
            'diagnostic_fixture': inventory.get('diagnostic_fixture') is True,
            'physical_completion': 'unverified_without_original_900_frame_motion',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'history_sha256': channels['history_sha256'],
            'channels_sha256': channels['channels_sha256'],
            'participants': {'ego_id': rows[0]['ego_id'], 'sign_id': rows[0]['sign_id']},
            'media': media, 'raw': raw}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic),
                     sort_keys=True))


if __name__ == '__main__':
    main()
