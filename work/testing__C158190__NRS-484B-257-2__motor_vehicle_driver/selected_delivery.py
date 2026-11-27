"""Read-only six-check selected yield delivery audit and diagnostic rejection."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import VIEWS, audit as audit_original


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, expected):
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


def audit(attempt, case, allow_diagnostic):
    attempt = Path(attempt).resolve()
    custody = audit_original(attempt, case)
    if custody['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('synthetic saved source cannot satisfy original delivery')
    history = [json.loads(line) for line in
               (attempt / 'original-attempt/history.jsonl').read_text().splitlines()]
    if not history or any(row['case_id'] != case or
                          not row['native_state'].get('ego_id') or
                          not row['native_state'].get('other_id') or
                          row['native_state']['ego_id'] == row['native_state']['other_id']
                          for row in history):
        raise ValueError('selected Native participants missing')
    source_dir = attempt / 'original-attempt/source-review'
    required = ('map_opendrive', 'intersection_geometry',
                'non_through_classification', 'all_entrance_controls',
                'ego_stop_sign', 'other_obligation')
    if custody['diagnostic_fixture'] and any(not (source_dir / (name + '.txt')).is_file()
                                             for name in required):
        raise ValueError('selected Native source review incomplete')
    if not custody['diagnostic_fixture'] and len(history) != 900:
        raise ValueError('original Native acquisition duration incomplete')
    media = {name: decode(attempt / (name + '.mkv'), len(history)) for name in VIEWS}
    media['raw'] = decode(attempt / 'raw.mkv', len(history))
    entry = float(json.loads((attempt / 'original-attempt/site-packet.json').read_text())
                  ['intersection_entry_station_m'])
    observed_entry = any(row['native_state'].get('ego_leading_station_m', float('-inf')) >= entry
                         for row in history)
    observed_clear = any(row['native_state'].get('ego_full_body_cleared') is True
                         for row in history)
    if not observed_entry or not observed_clear:
        raise ValueError('physical passage/clearance evidence missing')
    return {'format': 'worker-selected-yield-delivery-audit', 'case_id': case,
            'checks_executed': ['native_source', 'all_participants', 'time_join',
                                'full_video_decode', 'actual_pixels', 'physical_completion'],
            'diagnostic_fixture': custody['diagnostic_fixture'],
            'physical_completion': 'diagnostic_shape_only' if custody['diagnostic_fixture']
                                   else 'observed_pending_independent_review',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False,
            'source_custody': custody, 'media': media}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case, args.allow_diagnostic), sort_keys=True))
