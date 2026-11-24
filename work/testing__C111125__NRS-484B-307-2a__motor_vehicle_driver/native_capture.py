"""Original 20 Hz straight-green event acquisition with source-bound closure.

The caller owns world settings, actors, cameras and final restoration. This
module records their Native readbacks and never invents a lawful-presence fact.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from native_scene import require, source, verify_site
from saved_attempt import ASSIGNMENT, CASES, process_saved
from delivery_audit import VIEWS

FRAMES = 900


def capture(world, ego, other, site, site_ref, case_suffix, signal_reader,
            output_root, other_context_ref=None, camera_profile_sha256=None,
            camera_frame_reader=None):
    root = Path(output_root).resolve()
    if case_suffix not in CASES:
        raise ValueError('unknown exact case')
    if not callable(signal_reader):
        raise ValueError('original signal reader required')
    if not camera_profile_sha256:
        raise ValueError('source-hashed camera profile required')
    if camera_frame_reader is not None and not callable(camera_frame_reader):
        raise ValueError('original camera frame reader must be callable')
    verify_site(site, root)
    source(site_ref, root)
    if json.loads(source(site_ref, root).read_text()) != site:
        raise ValueError('site packet differs from source')
    kind, _ = CASES[case_suffix]
    if kind is None and other is not None or kind is not None and other is None:
        raise ValueError('other user differs from exact case')
    if kind is not None:
        if not other_context_ref:
            raise ValueError('reviewed other-user context source required')
        source(other_context_ref, root)
    if (root / 'original-events.json').exists() or (root / 'original-capture-receipt.json').exists():
        raise ValueError('original capture output already exists')
    rows = []
    frame_map = []
    try:
        for index in range(FRAMES):
            tick = world.tick()
            snapshot = world.get_snapshot()
            if snapshot.frame != tick:
                raise ValueError('Native tick and snapshot frame mismatch')
            instant = snapshot.timestamp.elapsed_seconds
            if type(instant) not in (int, float) or not math.isfinite(instant):
                raise ValueError('original Native time unavailable')
            if index and (tick != rows[-1]['frame'] + 1 or
                          not .04 <= instant - rows[-1]['elapsed_seconds'] <= .06):
                raise ValueError('original 20 Hz frame or time gap')
            signal = signal_reader(snapshot, site['official_head_id'])
            if (not isinstance(signal, dict) or
                    signal.get('head_id') != site['official_head_id'] or
                    signal.get('facing_approach_id') != site['ego_approach_id'] or
                    not isinstance(signal.get('lit_aspects'), list)):
                raise ValueError('original official facing signal unavailable')
            xy = ego.get_location()
            if any(not math.isfinite(v) for v in (xy.x, xy.y)):
                raise ValueError('original ego position unavailable')
            users = []
            if other is not None:
                where = other.get_location()
                if any(not math.isfinite(v) for v in (where.x, where.y)):
                    raise ValueError('original other-user position unavailable')
                users.append({'id': str(other.id), 'kind': kind,
                              'xy': [where.x, where.y],
                              'lawful_presence_source': other_context_ref['path']})
            rows.append({'frame': tick, 'elapsed_seconds': instant,
                         'official_head_id': signal['head_id'],
                         'facing_approach_id': signal['facing_approach_id'],
                         'lit_aspects': signal['lit_aspects'],
                         'ego_xy': [xy.x, xy.y], 'other_users': users})
            if camera_frame_reader is not None:
                camera_frames = camera_frame_reader(snapshot)
                if (not isinstance(camera_frames, dict) or
                        set(camera_frames) != set(VIEWS) or
                        any(type(camera_frames[view]) is not int or
                            camera_frames[view] != tick for view in VIEWS)):
                    raise ValueError('four original camera callbacks must join Native frame')
                frame_map.append({'index': index, 'frame': tick,
                                  'elapsed_seconds': instant,
                                  'camera_frame_ids': camera_frames.copy()})
    finally:
        # The caller still owns every actor and the world restoration.
        if hasattr(ego, 'set_target_velocity'):
            velocity = type(ego.get_velocity())
            ego.set_target_velocity(velocity(x=0.0, y=0.0, z=0.0))
    event_path = root / 'original-events.json'
    pending = root / 'original-events.json.pending'
    map_path = root / 'original-frame-map.json'
    map_pending = root / 'original-frame-map.json.pending'
    if pending.exists():
        raise ValueError('pending original events already exist')
    if frame_map and (map_path.exists() or map_pending.exists()):
        raise ValueError('original frame map already exists')
    raw = (json.dumps(rows, separators=(',', ':'), allow_nan=False) + '\n').encode()
    try:
        pending.write_bytes(raw)
        frame_map_ref = None
        if frame_map:
            map_raw = (json.dumps(frame_map, separators=(',', ':'), allow_nan=False) + '\n').encode()
            map_pending.write_bytes(map_raw)
            frame_map_ref = {'path': map_path.name,
                             'sha256': hashlib.sha256(map_raw).hexdigest()}
        event_ref = {'path': event_path.name, 'sha256': hashlib.sha256(raw).hexdigest()}
        packet = {'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT + '__' + case_suffix,
                  'case_suffix': case_suffix, 'candidate': 'primary',
                  'attempt_id': 'native-' + event_ref['sha256'][:16],
                  'recording_id': 'original-' + event_ref['sha256'][:16],
                  'site_ref': site_ref, 'event_ref': event_ref,
                  'duration_frames': FRAMES,
                  'camera_profile_sha256': camera_profile_sha256}
        # The saved analyzer resolves this final path. Retain original bytes
        # if validation fails; never publish a receipt for that acquisition.
        pending.replace(event_path)
        measured = process_saved(packet, root)
        if frame_map_ref is not None:
            map_pending.replace(map_path)
        receipt = {'format': 'c111125-original-green-capture', 'case_id': packet['case_id'],
                   'event_ref': event_ref, 'site_ref': site_ref,
                   'frame_map_ref': frame_map_ref,
                   'other_context_ref': other_context_ref,
                   'frame_count': FRAMES, 'first_frame': rows[0]['frame'],
                   'last_frame': rows[-1]['frame'], 'fps': 20,
                   'camera_capture_complete': False,
                   'physical_acceptance': False, 'legal_verdict': None}
        (root / 'original-capture-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return {'receipt': receipt, 'measurement': measured}
    finally:
        pending.unlink(missing_ok=True)
        map_pending.unlink(missing_ok=True)
