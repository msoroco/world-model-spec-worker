"""Capture original Native readback for the fixed C111125 straight route.

The adapter must read the simulator world after each synchronous tick. Authored
targets and requested controls cannot be substituted for these observations.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from signal_exception import SourceError, require, verify_site


def _sample(site, raw, previous_frame, previous_time):
    require(isinstance(raw, dict), 'Native snapshot missing')
    frame = raw.get('frame')
    time_s = raw.get('time_s')
    require(isinstance(frame, int) and frame == previous_frame + 1, 'Native frame gap')
    require(isinstance(time_s, (int, float)) and math.isfinite(time_s), 'Native time missing')
    if previous_time is not None:
        require(abs((time_s - previous_time) - 0.05) < 0.001, 'Native rate is not 20 Hz')
    require(raw.get('source_kind') == 'native_world_snapshot', 'non-Native sample')
    require(raw.get('official_head_id') == site['official_head_id'], 'official head drift')
    require(raw.get('facing_approach_id') == site['ego_approach_id'], 'approach drift')
    require(raw.get('actor_id') and raw.get('actor_type_id') == site['ego_blueprint_id'], 'ego identity drift')
    require(raw.get('lit_aspects') in (['steady_red', 'green_turn_arrow'], ['steady_red'], ['green_turn_arrow']), 'unreadable official aspect')
    for name in ('ego_front_station_m', 'speed_mps'):
        value = raw.get(name)
        require(isinstance(value, (int, float)) and math.isfinite(value), 'invalid Native ' + name)
    require(raw['speed_mps'] >= 0, 'negative Native speed')
    users = raw.get('other_users')
    require(isinstance(users, list), 'other-user Native inventory missing')
    for user in users:
        require(isinstance(user, dict) and user.get('actor_id') and user.get('region') in
                ('adjacent_crosswalk', 'intersection', 'outside'), 'invalid participant readback')
        require(user.get('source_kind') == 'native_world_snapshot', 'non-Native participant')
    return raw


def capture_original(site, source_root, adapter, output_path, *, frames=900, diagnostic_fixture=False,
                     on_frame=None):
    """Write one sealed event packet after exactly 45 s of 20 Hz readback.

    ``adapter.tick()`` advances synchronous Native time and returns a snapshot
    gathered from the new world frame. This worker module does not instantiate
    CARLA or assert physical visibility. The local runner must wire its adapter.
    """
    verify_site(site, source_root)
    require(frames == 900, 'full 45 second recording required')
    rows = []
    previous_frame = None
    previous_time = None
    actor_id = None
    for _ in range(frames):
        raw = adapter.tick()
        if previous_frame is None:
            require(isinstance(raw, dict) and isinstance(raw.get('frame'), int), 'first Native frame missing')
            previous_frame = raw['frame'] - 1
        row = _sample(site, raw, previous_frame, previous_time)
        if actor_id is None:
            actor_id = row['actor_id']
        require(row['actor_id'] == actor_id, 'ego actor changed')
        if on_frame is not None:
            on_frame(row)
        rows.append(row)
        previous_frame, previous_time = row['frame'], row['time_s']
    output = Path(output_path)
    require(output.parent.resolve() == Path(source_root).resolve(), 'event output must share source root')
    output.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(rows, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8')
    output.write_bytes(data)
    return {
        'event_ref': {'path': str(output.name), 'sha256': hashlib.sha256(data).hexdigest()},
        'frame_first': rows[0]['frame'], 'frame_last': rows[-1]['frame'],
        'frame_count': frames, 'actor_id': actor_id,
        'official_head_id': site['official_head_id'],
        'diagnostic_fixture': diagnostic_fixture,
        'physical_acceptance_claimed': False,
    }
