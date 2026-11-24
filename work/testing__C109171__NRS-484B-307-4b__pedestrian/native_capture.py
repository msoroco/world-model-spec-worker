"""Source-gated Native capture writer for the four C109171 pedestrian cases.

The adapter supplies original simulator events and sensor PNG payloads. This writer
never labels synthetic payloads as physical evidence or infers legal permission.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path

from PIL import Image

from native_scene import SourceError, verify_site
from saved_measurement import ASSIGNMENT, EXPECTED, measure_saved

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FPS = 20
DEFAULT_FRAMES = 900


def _require(ok, message):
    if not ok:
        raise SourceError(message)


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return {'path': path.name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def _png_bytes(raw):
    _require(isinstance(raw, bytes) and raw, 'missing original camera bytes')
    with Image.open(io.BytesIO(raw)) as im:
        im.verify()
        _require(im.format == 'PNG', 'camera payload is not PNG')
    with Image.open(io.BytesIO(raw)) as im:
        im.load()
        _require(im.width > 0 and im.height > 0, 'empty camera image')


def capture(site, site_ref, attempt, adapter, case_id, expected_frames=DEFAULT_FRAMES):
    """Record exact events and four PNG sources from a Native adapter.

    Adapter contract: start(site, case_id); read(frame) -> {'event': dict,
    'cameras': {name: {'frame': int, 'png': bytes}}}; close(). The adapter owns
    CARLA resource restoration and must attest original simulator provenance.
    """
    attempt = Path(attempt).resolve()
    _require(case_id.startswith(ASSIGNMENT + '__'), 'case outside assignment')
    _require(case_id.removeprefix(ASSIGNMENT + '__') in EXPECTED, 'unknown exact case')
    _require(isinstance(expected_frames, int) and expected_frames > 1, 'invalid capture length')
    _require(attempt.is_dir(), 'attempt directory missing')
    _require(site.get('source_kind') == 'native_original', 'diagnostic site rejected')
    _require(site_ref.get('path') and site_ref.get('sha256'), 'original site ref required')
    site_path = (attempt / site_ref['path']).resolve()
    _require(site_path.is_relative_to(attempt) and site_path.is_file(), 'site source outside attempt')
    _require(hashlib.sha256(site_path.read_bytes()).hexdigest() == site_ref['sha256'], 'site hash mismatch')
    _require(json.loads(site_path.read_text(encoding='utf-8')) == site, 'site packet differs')
    verify_site(site, attempt)
    rows = []
    frame_map = []
    media_root = attempt / 'camera_png'
    media_root.mkdir(exist_ok=False)
    adapter.start(site, case_id)
    try:
        for frame in range(expected_frames):
            sample = adapter.read(frame)
            _require(isinstance(sample, dict), 'adapter sample missing')
            row = sample.get('event')
            cameras = sample.get('cameras')
            _require(isinstance(row, dict) and row.get('frame') == frame, 'original event frame drift')
            t = row.get('sim_time_seconds')
            _require(isinstance(t, (int, float)) and math.isfinite(t), 'original event time missing')
            if frame:
                _require(abs((t - rows[-1]['sim_time_seconds']) - 1 / FPS) < 1e-4,
                         'original event clock drift')
            _require(isinstance(cameras, dict) and set(cameras) == set(CAMERAS),
                     'four original camera callbacks required')
            mapped = {'frame': frame, 'sim_time_seconds': t, 'cameras': {}}
            for name in CAMERAS:
                item = cameras[name]
                _require(isinstance(item, dict) and item.get('frame') == frame,
                         'camera callback frame drift: ' + name)
                raw = item.get('png')
                _png_bytes(raw)
                rel = Path('camera_png') / (f'{frame:04d}_{name}.png')
                path = attempt / rel
                path.write_bytes(raw)
                mapped['cameras'][name] = {
                    'path': rel.as_posix(), 'sha256': hashlib.sha256(raw).hexdigest()
                }
            rows.append(row)
            frame_map.append(mapped)
    finally:
        adapter.close()
    events_ref = _write_json(attempt / 'original_events.json', rows)
    map_ref = _write_json(attempt / 'original_frame_map.json', frame_map)
    measurement = measure_saved(attempt, site_ref, events_ref, case_id, expected_frames)
    return {'case_id': case_id, 'events_ref': events_ref, 'frame_map_ref': map_ref,
            'measurement': measurement, 'camera_count': len(CAMERAS),
            'frame_count': expected_frames, 'physical_acceptance': False,
            'legal_verdict': None}


def audit_frame_map(attempt, frame_map_ref, events_ref, expected_frames=DEFAULT_FRAMES):
    """Reopen every saved camera byte string and verify event/sensor joins."""
    attempt = Path(attempt).resolve()
    def read(ref):
        path = (attempt / ref['path']).resolve()
        _require(path.is_relative_to(attempt) and path.is_file(), 'missing source')
        _require(hashlib.sha256(path.read_bytes()).hexdigest() == ref['sha256'], 'source hash mismatch')
        return json.loads(path.read_text(encoding='utf-8'))
    mapping = read(frame_map_ref)
    events = read(events_ref)
    _require(len(mapping) == len(events) == expected_frames, 'incomplete original capture')
    for frame, (mapped, row) in enumerate(zip(mapping, events)):
        _require(mapped['frame'] == row['frame'] == frame, 'event/camera frame drift')
        _require(mapped['sim_time_seconds'] == row['sim_time_seconds'], 'event/camera time drift')
        if frame:
            _require(abs((row['sim_time_seconds'] - events[frame-1]['sim_time_seconds'])
                         - 1 / FPS) < 1e-4, 'saved original clock drift')
        _require(set(mapped['cameras']) == set(CAMERAS), 'camera missing from frame map')
        for name in CAMERAS:
            ref = mapped['cameras'][name]
            expected_path = f'camera_png/{frame:04d}_{name}.png'
            _require(ref.get('path') == expected_path,
                     'camera source frame/channel path differs')
            path = (attempt / ref['path']).resolve()
            _require(path.is_relative_to(attempt) and path.is_file(), 'camera source missing')
            raw = path.read_bytes()
            _require(hashlib.sha256(raw).hexdigest() == ref['sha256'], 'camera source hash mismatch')
            _png_bytes(raw)
    return {'frames_audited': expected_frames, 'camera_frames_audited': 4 * expected_frames,
            'physical_acceptance': False, 'legal_verdict': None}
