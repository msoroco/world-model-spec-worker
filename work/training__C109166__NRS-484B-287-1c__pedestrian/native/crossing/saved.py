"""Source-only crossing diagnostic; never an original Native or legal verdict."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import subprocess

from request import CASES, FRAMES, RATE, sha


CAMERAS = ('overview', 'approach', 'crosswalk', 'devices')


def load_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError('Missing saved source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines()]


def decoded_frames(path: Path) -> int:
    if not path.is_file():
        raise ValueError('Missing source camera: ' + path.name)
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_read_frames',
         '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        text=True, capture_output=True, timeout=120)
    if result.returncode or not result.stdout.strip().isdigit():
        raise ValueError('Source camera decode failed: ' + path.name)
    return int(result.stdout.strip())


def decoded_pixel_sha256(path: Path) -> str:
    result = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(path),
         '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
        capture_output=True, timeout=120)
    if result.returncode or len(result.stdout) != FRAMES * 32 * 32 * 3:
        raise ValueError('Source camera full pixel decode failed: ' + path.name)
    return hashlib.sha256(result.stdout).hexdigest()


def inspect(attempt: Path) -> dict:
    attempt = Path(attempt)
    cfg = json.loads((attempt / 'config.json').read_text())
    if (cfg.get('requested_crossing_location') not in CASES or
            cfg.get('case_id') != cfg.get('assignment_id', '') + '__' +
            cfg['requested_crossing_location'] or cfg.get('frames') != FRAMES or
            cfg.get('duration_s') != 30 or cfg.get('rate_hz') != RATE):
        raise ValueError('Saved case or duration differs')
    manifest = json.loads((attempt / 'capture-manifest.json').read_text())
    if manifest.get('source_kind') != 'synthetic_native_sample':
        raise ValueError('Diagnostic source kind differs')
    names = ('frame-map.jsonl', 'pedestrian.jsonl', 'devices.jsonl',
             'map-readback.json') + tuple(name + '.mkv' for name in CAMERAS)
    if set(manifest.get('sha256', {})) != set(names):
        raise ValueError('Saved source inventory differs')
    for name in names:
        path = attempt / name
        if not path.is_file() or sha(path) != manifest['sha256'][name]:
            raise ValueError('Saved source hash differs: ' + name)
    mapping, walker, devices = (load_rows(attempt / name) for name in names[:3])
    topology = json.loads((attempt / 'map-readback.json').read_text())
    if not (topology.get('roadway_y_bounds_m') == [-4, 4] and
            topology.get('intersection_x_m') == [0, 100] and
            topology.get('connected_no_intermediate_intersection') is True and
            topology.get('crosswalk_marking_x_m') == 40 and
            topology.get('source_kind') == 'synthetic_native_sample'):
        raise ValueError('Saved adjacent-intersection topology differs')
    if any(len(group) != FRAMES for group in (mapping, walker, devices)):
        raise ValueError('Saved frame count differs')
    entry = None
    for index, (frame, ped, control) in enumerate(zip(mapping, walker, devices)):
        expected_time = (index + 1) / RATE
        native = frame.get('native_frame')
        if (frame.get('video_frame') != index or type(native) is not int or
                frame.get('carla_frame') != native or native != index + 1000 or
                abs(frame.get('time_s', -1) - expected_time) > 1e-8):
            raise ValueError('Saved frame identity or time differs')
        if (ped.get('native_frame') != native or control.get('native_frame') != native or
                abs(ped.get('time_s', -1) - expected_time) > 1e-8 or
                abs(control.get('time_s', -1) - expected_time) > 1e-8):
            raise ValueError('Saved participant/time join differs')
        x, y = ped.get('footprint_center_xy_m', [None, None])
        if (type(x) not in (float, int) or type(y) not in (float, int) or
                not math.isfinite(x) or not math.isfinite(y) or
                abs(x - CASES[cfg['requested_crossing_location']]) > 1e-8):
            raise ValueError('Saved pedestrian footprint differs')
        if entry is None and y >= -4:
            entry = index
        if (control.get('intersection_ids') != [101, 102] or
                control.get('official_device_ids') != [201, 202] or
                control.get('operating') != [True, True]):
            raise ValueError('Saved official devices not operating')
    if entry != 259 or walker[-1]['footprint_center_xy_m'][1] < 4:
        raise ValueError('Saved roadway crossing event differs')
    videos = {name: decoded_frames(attempt / (name + '.mkv')) for name in CAMERAS}
    if any(count != FRAMES for count in videos.values()):
        raise ValueError('Saved four-camera frame count differs')
    pixel_hashes = {name: decoded_pixel_sha256(attempt / (name + '.mkv'))
                    for name in CAMERAS}
    marked = cfg['requested_crossing_location'] == 'marked_crosswalk'
    return {'format': 'c109166-saved-crossing-diagnostic-v1',
            'case_id': cfg['case_id'], 'source_kind': 'synthetic_native_sample',
            'frame_count': FRAMES, 'duration_s': 30,
            'roadway_entry_frame': entry,
            'adjacent_topology_in_diagnostic_source': True,
            'both_official_devices_operating_at_entry': True,
            'marked_crosswalk_at_entry_in_diagnostic_source': marked,
            'videos_decoded': videos,
            'decoded_pixel_sha256': pixel_hashes,
            'source_sha256': manifest['sha256'],
            'original_native_observed': False, 'physical_acceptance': False,
            'legal_verdict': None}
