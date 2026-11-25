"""Seal exact saved bicycle originals for later independent delivery audit.

Run after Native capture and camera encoding; this code never creates evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from bicycle_encounter import ASSIGNMENT, CASE_VARIANTS, require
from saved_attempt import VIEWS


def _ref(root, path):
    path = Path(path).resolve()
    require(path.is_relative_to(root) and path.is_file() and not path.is_symlink(),
            'original source missing or escaping')
    return {'path': path.relative_to(root).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build(root, case_id, *, expected_frames=900):
    root = Path(root).resolve()
    require(root.is_dir(), 'saved original attempt missing')
    require(case_id in {ASSIGNMENT + '__' + suffix for suffix in CASE_VARIANTS},
            'wrong exact bicycle case')
    require(isinstance(expected_frames, int) and expected_frames >= 3,
            'invalid original frame count')
    index_path = root / 'source-index.json'
    require(not index_path.exists(), 'source index already exists')
    site = json.loads((root / 'site.json').read_text(encoding='utf-8'))
    events = json.loads((root / 'events.json').read_text(encoding='utf-8'))
    frame_map = [json.loads(line) for line in
                 (root / 'video_frames.jsonl').read_text(encoding='utf-8').splitlines()]
    require(site.get('assignment_id') == ASSIGNMENT and
            site.get('case_id') == case_id, 'original site case mismatch')
    require(len(events) == len(frame_map) == expected_frames,
            'original event/frame map count mismatch')
    first_time = frame_map[0].get('time_s')
    require(isinstance(first_time, (int, float)) and math.isfinite(first_time),
            'original timebase missing')
    for number, (event, row) in enumerate(zip(events, frame_map)):
        require(row.get('video_frame') == number and
                row.get('native_frame') == event.get('frame') and
                row.get('carla_frame') == event.get('frame') and
                event.get('camera_frame') == event.get('frame') and
                isinstance(row.get('time_s'), (int, float)) and
                math.isfinite(row['time_s']) and
                abs(row['time_s'] - first_time - number / 20) < 1e-4,
                'original event/frame map identity mismatch')
    refs = {key: _ref(root, root / filename) for key, filename in
            (('site', 'site.json'), ('events', 'events.json'),
             ('frame_map', 'video_frames.jsonl'))}
    originals = {}
    for view in VIEWS:
        videos = [root / (view + suffix) for suffix in ('.mkv', '.mp4')]
        present = [path for path in videos if path.is_file()]
        require(len(present) == 1, 'one encoded original video required: ' + view)
        refs[view] = _ref(root, present[0])
        view_dir = root / 'camera-originals' / view
        require(view_dir.is_dir() and not view_dir.is_symlink(),
                'original camera image directory missing: ' + view)
        files = sorted(view_dir.glob('*.png'))
        require(len(files) == expected_frames,
                'original camera image count mismatch: ' + view)
        originals[view] = []
        for event, row, path in zip(events, frame_map, files):
            require(path.name == f"{event['frame']:08d}.png",
                    'original camera image identity mismatch: ' + view)
            originals[view].append({'frame': event['frame'],
                                    'time_s': row['time_s'],
                                    'image': _ref(root, path)})
    packet = {'format': 'c111260-original-index-v1',
              'case_id': case_id, 'frame_count': expected_frames,
              'sources': refs, 'camera_originals': originals}
    index_path.write_text(json.dumps(packet, indent=2) + '\n', encoding='utf-8')
    return packet
