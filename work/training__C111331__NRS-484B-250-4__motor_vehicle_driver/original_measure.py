"""Source-only measurements of an original C111331 Native attempt.

Engineering speed/frame probes are reported as measurements, never statutory
definitions of a complete stop, cautious entry, yielding, or signal authority.
"""
import hashlib
import json
from pathlib import Path

SOURCES = ('native-raw-actors.jsonl', 'native-signal-readback.jsonl',
           'native-map-readback.json', 'video_frames.jsonl')
LINE_X = -26.0
ENTRY_X = -20.0


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines()]


def measure(attempt):
    attempt = Path(attempt)
    for name in SOURCES:
        if not (attempt / name).is_file():
            raise ValueError('Missing required original source: ' + name)
    mapping = json.loads((attempt / 'native-map-readback.json').read_text())
    if (mapping.get('source_kind') != 'original_native' or
            mapping.get('incoming') != {'250': {'line_x_m': LINE_X},
                                       '253': {'line_y_m': LINE_X}}):
        raise ValueError('Original map and marked-line readback differs')
    actor = rows(attempt / 'native-raw-actors.jsonl')
    signal = rows(attempt / 'native-signal-readback.jsonl')
    video = rows(attempt / 'video_frames.jsonl')
    if any(len(stream) != 600 for stream in (actor, signal, video)):
        raise ValueError('Complete 600-frame original source join required')
    stop_frames = []
    ego_entry = None
    other_entry = None
    other_stop = None
    for i, (a, s, v) in enumerate(zip(actor, signal, video)):
        if (a.get('frame') != i or s.get('frame') != i or
                v.get('video_frame') != i or
                a.get('native_frame') != v.get('native_frame') or
                abs(a.get('time_s', -100) - s.get('time_s', -200)) > .051 or
                abs(a.get('time_s', -100) - v.get('time_s', -200)) > .051):
            raise ValueError('Original actor/signal/video frame join differs')
        if (a.get('source_kind') != 'original_native' or
                s.get('source_kind') != 'original_native' or
                set(s.get('governing_heads', {})) != {'250:-1', '253:-1'} or
                any(head.get('state') != 'Off' or head.get('light_box_count', 0) < 1
                    for head in s['governing_heads'].values())):
            raise ValueError('Original Off signal readback absent or contradicted')
        ego, other = a.get('ego', {}), a.get('other', {})
        if (not ego.get('body_native_xyz_m') or not other.get('body_native_xyz_m') or
                not isinstance(ego.get('speed_mps'), (int, float)) or
                not isinstance(other.get('speed_mps'), (int, float))):
            raise ValueError('Original body or speed source missing')
        ego_front = max(point[0] for point in ego['body_native_xyz_m'])
        other_front = max(point[1] for point in other['body_native_xyz_m'])
        if ego_front < LINE_X and ego['speed_mps'] < .05:
            stop_frames.append(i)
        if other_front < LINE_X and other['speed_mps'] < .05 and other_stop is None:
            other_stop = i
        if ego_front >= ENTRY_X and ego_entry is None:
            ego_entry = i
        if other_front >= ENTRY_X and other_entry is None:
            other_entry = i
    if ego_entry is None or other_entry is None:
        raise ValueError('Original vehicles did not enter the junction')
    return {'frames': 600, 'pre_line_low_speed_frames': stop_frames,
            'ego_entry_frame': ego_entry, 'other_entry_frame': other_entry,
            'other_pre_line_low_speed_first_frame': other_stop,
            'source_sha256': {name: sha(attempt / name) for name in SOURCES},
            'speed_probe_mps': .05, 'speed_probe_is_statutory_threshold': False,
            'actual_pixels_reviewed': False, 'legal_verdict': None}
