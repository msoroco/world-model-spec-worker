"""Acquire synchronized original camera sources during the Native case ticks.

The adapter owns pixel encoding. This layer requires frame joins and original
source files, then leaves full decode and pixel review to independent audits.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from independent_delivery_audit import CAMERAS
from native_history_capture import capture_original_history
from parking import CASES, build_case
from reviewed_site import verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(adapter, packet_path: Path, source_root: Path, case_id: str,
            body_length_m: float, attempt: Path) -> dict:
    packet = verify(packet_path, source_root)
    prefix = packet['assignment_id'] + '__'
    if not case_id.startswith(prefix):
        raise ValueError('camera capture exact assignment differs')
    case = next((item for item in CASES if item.id == case_id[len(prefix):]), None)
    if case is None:
        raise ValueError('camera capture exact case missing')
    attempt = Path(attempt)
    if attempt.exists():
        raise ValueError('refusing to overwrite original camera attempt')
    site = dict(packet['site'])
    site['site_sha256'] = _sha(Path(packet_path))
    attempt.mkdir(parents=True)
    built = None
    started = False
    completed = False
    try:
        built = build_case(adapter, site, case, body_length_m)
        adapter.start_cameras(attempt, site['camera_plan_sha256'], CAMERAS)
        started = True
        mapping = []

        def record(row, index):
            camera_frames = adapter.record_camera_frame(row)
            if camera_frames != {name: index for name in CAMERAS}:
                raise ValueError('original camera frame index join differs')
            mapping.append({'original_frame': row['original_frame'],
                            'time_s': row['time_s'], 'camera_frames': camera_frames})

        history = capture_original_history(adapter, site, case,
                                           attempt / 'history.jsonl', frame_hook=record)
        if len(mapping) != 900:
            raise ValueError('original camera map incomplete')
        paths = adapter.finish_cameras()
        if not isinstance(paths, dict) or set(paths) != set(CAMERAS):
            raise ValueError('four original camera outputs missing')
        for name, path in paths.items():
            path = Path(path).resolve()
            if path != (attempt / (name + '.mkv')).resolve() or not path.is_file() or not path.stat().st_size:
                raise ValueError('original camera file missing: ' + name)
        context = adapter.original_comparison_context()
        if not isinstance(context, dict):
            raise ValueError('original comparison context missing')
        expected = {'format': 'sidewalk-elevator-original-comparison-context',
                    'case_id': case_id, 'site_packet_sha256': site['site_sha256'],
                    'history_sha256': history['sha256'],
                    'ego_blueprint_sha256': site['ego_blueprint_sha256'],
                    'route_sha256': site['one_way_direction_sha256']}
        if any(context.get(key) != value for key, value in expected.items()) or not context.get('weather_sha256'):
            raise ValueError('original comparison context source differs')
        exception_key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                         'police_direction': 'police_direction_source_sha256',
                         'traffic_device_direction': 'traffic_device_source_sha256'}.get(case.exception)
        if context.get('exception_source_sha256') != (site.get(exception_key) if exception_key else None):
            raise ValueError('original comparison exception source differs')
        curb = context.get('curb_gap_target_m')
        if type(curb) not in (int, float) or not math.isfinite(curb) or curb < 0:
            raise ValueError('original comparison curb target missing')
        (attempt / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(item, sort_keys=True) + '\n' for item in mapping))
        (attempt / 'comparison-context.json').write_text(json.dumps(context, sort_keys=True) + '\n')
        completed = True
        return {'case_id': case_id, 'site_packet_sha256': site['site_sha256'],
                'history_sha256': history['sha256'],
                'camera_frame_map_sha256': _sha(attempt / 'camera-frame-map.jsonl'),
                'comparison_context_sha256': _sha(attempt / 'comparison-context.json'),
                'camera_sha256': {name: _sha(Path(paths[name])) for name in CAMERAS},
                'frame_count': 900, 'full_video_decode': False,
                'physical_visibility_verified': False, 'legal_judgment': None}
    finally:
        if started and not completed:
            adapter.abort_cameras()
        if built is not None:
            for actor in reversed(built['owned']):
                adapter.destroy(actor)
