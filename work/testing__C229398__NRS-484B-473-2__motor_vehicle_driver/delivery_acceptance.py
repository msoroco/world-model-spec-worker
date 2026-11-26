"""Independent exact-case parked-light delivery audit for saved Native outputs."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from analysis import measure, required
from capture_seal import CAMERAS
from parked_lamps import valid_number


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decode(path, frames):
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                            '-select_streams', 'v:0', '-show_entries',
                            'stream=width,height,nb_read_frames,r_frame_rate',
                            '-of', 'json', str(path)], capture_output=True,
                           text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or streams[0].get('r_frame_rate') != '20/1' or \
            int(streams[0].get('nb_read_frames', -1)) != frames:
        raise ValueError('full saved video metadata differs: ' + path.name)
    result = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path),
                             '-f', 'null', '-'], capture_output=True, text=True)
    if result.returncode:
        raise ValueError('full saved video decode failed: ' + path.name)
    return {'sha256': sha(path), 'frames': frames,
            'dimensions': [streams[0]['width'], streams[0]['height']]}


def audit(case_id, attempt, plan):
    attempt, plan = Path(attempt), Path(plan)
    planned = json.loads(plan.read_text())
    if case_id not in {item['case_id'] for item in planned['cases']}:
        raise ValueError('delivery case outside exact parked-light plan')
    measured_case, case, scene, ticks, trace, checked, diagnostic = measure(attempt)
    if measured_case != case_id:
        raise ValueError('delivery case differs from saved original source')
    if len({tick['vehicle_id'] for tick in ticks}) != 1 or \
            any(not valid_number(tick['speed_mps']) for tick in ticks):
        raise ValueError('original vehicle identity or physical speed incomplete')
    expected = {'overview': [1920, 1080], 'approach': [1280, 720],
                'reference_corner': [1280, 720], 'driver_reference': [1280, 720]}
    videos = {}
    for name in CAMERAS:
        item = decode(required(attempt, name + '.mkv'), len(ticks))
        if item['dimensions'] != expected[name]:
            raise ValueError('saved camera dimensions differ: ' + name)
        videos[name] = item
    return {'format': 'c229398-independent-delivery-acceptance-v1',
            'case_id': case_id, 'source_kind': checked['source_kind'],
            'diagnostic_fixture': diagnostic,
            'source_packet_sha256': checked['packet_sha256'],
            'original_ticks_sha256': sha(attempt / 'original-ticks.jsonl'),
            'video_frame_map_sha256': sha(attempt / 'video_frames.jsonl'),
            'source_frames': len(ticks), 'videos': videos,
            'all_participants_joined': True,
            'physical_stationary_interval_observed': all(
                row['speed_mps'] <= .1 for row in ticks[scene['park_start_frame']:]),
            'four_view_full_decode': True,
            'actual_pixels_decoded': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


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
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(receipt['case_id'])
