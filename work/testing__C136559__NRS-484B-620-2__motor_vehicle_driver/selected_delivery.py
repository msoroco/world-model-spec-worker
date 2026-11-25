"""Independent selected speed-zone delivery audit and diagnostic rejection."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from delivery_audit import VIEWS, audit as audit_custody


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, count):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                            '-count_frames', '-show_entries',
                            'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
                           text=True, capture_output=True, check=True)
    streams = json.loads(probe.stdout)['streams']
    if len(streams) != 1 or int(streams[0]['nb_read_frames']) != count or \
            min(int(streams[0]['width']), int(streams[0]['height'])) < 16:
        raise ValueError('selected speed video frames/pixels differ: ' + path.name)
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                              '-map', '0:v:0', '-f', 'framemd5', '-'],
                             text=True, capture_output=True, check=True)
    pixels = [line for line in decoded.stdout.splitlines()
              if line and not line.startswith('#')]
    if len(pixels) != count or any(len(line.split(',')) < 6 for line in pixels):
        raise ValueError('selected speed decoded pixel inventory differs: ' + path.name)
    return {'sha256': sha(path), 'frames': count,
            'pixel_digest_sha256': hashlib.sha256(decoded.stdout.encode()).hexdigest()}


def audit(attempt, case_id, allow_diagnostic=False):
    attempt = Path(attempt).resolve()
    custody = audit_custody(attempt, case_id)
    if custody['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('synthetic saved source cannot satisfy original delivery')
    capture = json.loads((attempt / 'original-attempt/capture.json').read_text())
    history = capture['original_rows']
    if len(history) != custody['original_frames']:
        raise ValueError('selected speed history differs')
    if not custody['diagnostic_fixture'] and len(history) != 900:
        raise ValueError('original Native speed acquisition duration incomplete')
    if any(not row.get('ego_id') or not row.get('sign_readback_source_sha256')
           for row in history):
        raise ValueError('selected speed participant/sign evidence missing')
    media = {name: decode(attempt / (name + '.mkv'), len(history)) for name in VIEWS}
    media['raw'] = decode(attempt / 'raw.mkv', len(history))
    return {'format': 'worker-selected-speed-delivery-audit', 'case_id': case_id,
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
