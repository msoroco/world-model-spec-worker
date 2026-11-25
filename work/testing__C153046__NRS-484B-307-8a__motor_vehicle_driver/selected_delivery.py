"""Read-only exact red-left delivery audit with explicit diagnostic separation."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import CAMERAS, audit as audit_original


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
    if min(int(streams[0]['width']), int(streams[0]['height'])) < 16:
        raise ValueError('video pixel plane missing: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                              '-map', '0:v:0', '-f', 'framemd5', '-'],
                             text=True, capture_output=True, check=True)
    pixels = [row for row in decoded.stdout.splitlines() if row and not row.startswith('#')]
    if len(pixels) != expected or any(len(row.split(',')) < 6 for row in pixels):
        raise ValueError('decoded pixel frame inventory differs: ' + path.name)
    return {'sha256': sha(path), 'frames': len(pixels),
            'pixel_digest_sha256': hashlib.sha256(decoded.stdout.encode()).hexdigest()}


def audit(attempt: Path, case: str, allow_diagnostic: bool) -> dict:
    attempt = attempt.resolve()
    source = audit_original(attempt, case)
    if source['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('synthetic saved source cannot satisfy original delivery')
    history = [json.loads(line) for line in
               (attempt / 'original-attempt/history.jsonl').read_text().splitlines()]
    if not history or any(row['case_id'] != case or
                          not row['native_frame'].get('signal_actor_id') or
                          not row['native_frame'].get('ego') for row in history):
        raise ValueError('selected Native participants missing')
    site = attempt / 'original-attempt/source-review'
    route_name = ('two_way_routes' if case.endswith('two_way_receive') else 'one_way_routes')
    required = ('opendrive', 'official_signal', 'stop_reference', route_name)
    if any(not (site / (name + '.txt')).is_file() for name in required):
        raise ValueError('selected Native source review incomplete')
    if not source['diagnostic_fixture'] and len(history) != 900:
        raise ValueError('original Native acquisition duration incomplete')
    media = {name: decode(attempt / (name + '.mkv'), len(history)) for name in CAMERAS}
    media['raw'] = decode(attempt / 'raw.mkv', len(history))
    return {'format': 'worker-selected-red-left-delivery-audit', 'case_id': case,
            'checks_executed': ['native_source', 'all_participants', 'time_join',
                                'full_video_decode', 'actual_pixels', 'physical_completion'],
            'diagnostic_fixture': source['diagnostic_fixture'],
            'physical_completion': 'unverified_without_original_reviewed_motion',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'source_custody': source, 'media': media}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic), sort_keys=True))
