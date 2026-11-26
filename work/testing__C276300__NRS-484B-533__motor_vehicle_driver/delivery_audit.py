"""Independent source and full-video check for an exact grade-standing attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure_saved, required

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
DIMENSIONS = {'overview': (1920, 1080), 'approach': (1280, 720),
              'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def full_decode(path, frames, dimensions):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                          '-select_streams', 'v:0', '-show_entries',
                          'stream=width,height,nb_read_frames,r_frame_rate',
                          '-of', 'json', str(path)], capture_output=True,
                         text=True, check=True)
    streams = json.loads(run.stdout).get('streams', [])
    if len(streams) != 1:
        raise ValueError('saved video stream count differs: ' + path.name)
    stream = streams[0]
    if ([int(stream['width']), int(stream['height'])] != list(dimensions) or
            stream['r_frame_rate'] != '20/1' or
            int(stream['nb_read_frames']) != frames):
        raise ValueError('saved video dimensions, rate or frames differ: ' + path.name)
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                             '-f', 'null', '-'], capture_output=True, text=True)
    if decode.returncode:
        raise ValueError('full saved video decode failed: ' + path.name)
    return {'sha256': sha(path), 'frames': frames,
            'dimensions': list(dimensions)}


def audit(case_id, attempt, plan):
    attempt, plan = Path(attempt), Path(plan)
    planned = json.loads(plan.read_text())
    if case_id not in {item['case_id'] for item in planned['cases']}:
        raise ValueError('delivery case outside exact plan')
    measured_case, measurement, rows, construction, checked = measure_saved(attempt)
    if measured_case != case_id:
        raise ValueError('delivery case differs from original source')
    if len({row['ego_id'] for row in rows}) != 1 or \
            len({row['other_id'] for row in rows}) != 1:
        raise ValueError('original participant identity incomplete')
    original = [row['original_frame'] for row in rows]
    if len(original) != len(set(original)) or original != sorted(original):
        raise ValueError('original frame sequence differs')
    videos = {name: full_decode(required(attempt, name + '.mkv'), len(rows),
                                DIMENSIONS[name]) for name in CAMERAS}
    return {'format': 'c276300-independent-delivery-audit-v1',
            'case_id': case_id, 'source_kind': checked['source_kind'],
            'diagnostic_fixture': checked['source_kind'] == 'diagnostic_fixture',
            'source_packet_sha256': sha(attempt / ('reviewed-packet.json' if
                checked['source_kind'] == 'diagnostic_fixture' else 'source-packet.json')),
            'original_ticks_sha256': sha(attempt / 'original-ticks.jsonl'),
            'video_frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'source_frames': len(rows), 'videos': videos,
            'all_participants_joined': True, 'time_joined': True,
            'physical_standing_frames_measured': measurement['standing_frame_count'],
            'four_view_full_decode': True, 'actual_pixels_decoded': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('retain prior audit; choose a fresh output')
    receipt = audit(args.case_id, args.attempt, args.plan)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(receipt['case_id'])
