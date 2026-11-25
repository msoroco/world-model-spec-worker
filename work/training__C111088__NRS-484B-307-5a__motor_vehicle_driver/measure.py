"""Saved-source measurements for the sole straight arrow proposal.

These measurements describe a captured attempt. They do not decide whether an
actor was legally entitled to enter, or whether CARLA displayed the authored
arrow. Those facts require separately retained Native and pixel evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from geometry import CROSSWALK, INTERSECTION, STOP_LINE_Y, overlap


def source_rows(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"Missing original source: {path}")
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError(f"Empty original source: {path}")
    return rows


def joined_samples(attempt: Path, *, rate_hz: int = 20, duration_s: int = 42) -> tuple[list[dict], dict]:
    """Require exact one-to-one original Native, body, capture and video joins."""
    names = ('native_samples.jsonl', 'body_history.jsonl', 'video_frames.jsonl',
             'trace.jsonl', 'capture/evidence.jsonl')
    groups = [source_rows(attempt / name) for name in names]
    count = rate_hz * duration_s
    if any(len(group) != count for group in groups):
        raise ValueError('Original source frame count differs from 42-second contract')
    native, bodies, mapping, trace, evidence = groups
    previous_frame = -1
    previous_time = -math.inf
    for index, (sample, body, video, core, captured) in enumerate(zip(*groups)):
        frame = sample.get('native_frame')
        time = sample.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or not math.isfinite(time):
            raise ValueError('Invalid original Native frame or time')
        if frame <= previous_frame or time <= previous_time:
            raise ValueError('Original Native frames or times not increasing')
        previous_frame, previous_time = frame, time
        if video.get('video_frame') != index or video.get('native_frame') != frame:
            raise ValueError('Original video frame mapping differs')
        if any(row.get(key) != frame for row, key in
               ((body, 'frame'), (core, 'frame'), (captured, 'original_frame'))):
            raise ValueError('Original full-body/Core frame join differs')
        if any(abs(row.get(key, math.inf) - time) > 1e-4 for row, key in
               ((body, 'time_s'), (video, 'time_s'), (core, 'time_s'),
                (captured, 'recording_time_s'))):
            raise ValueError('Original full-body/Core time join differs')
        vertices = sample.get('native_body_xy_m')
        if not isinstance(vertices, list) or len(vertices) != 4:
            raise ValueError('Original Native four-corner body missing')
        original = {(round(v[0], 4), round(v[1], 4)) for v in vertices}
        history = {(round(v[0], 4), round(v[1], 4)) for v in body.get('body_vertices_m', [])}
        capture = {(round(v[0], 4), round(v[1], 4)) for v in
                   captured.get('ego', {}).get('body_vertices_m', [])}
        if len(original) != 4 or original != history or original != capture:
            raise ValueError('Original Native body/capture footprint differs')
    return native, {'frames': count, 'first_native_frame': native[0]['native_frame'],
                    'last_native_frame': native[-1]['native_frame'],
                    'source_sha256': {name: hashlib.sha256((attempt / name).read_bytes()).hexdigest()
                                      for name in names}}


def measure_arrow_and_yield(samples: list[dict], *, verified_arrow_frames: set[int] | None = None) -> dict:
    """Measure stop-line crossing relative to actual saved actor occupancy.

    `signal_aspect_source` records provenance. An authored OpenDRIVE subtype is
    insufficient to establish that the displayed head showed a sole arrow.
    """
    if not samples:
        raise ValueError('No original samples')
    active = []
    verified_arrow_frames = verified_arrow_frames or set()
    crossings = []
    forbidden_turn = []
    occupancies = []
    prior_front = None
    initial_yaw = None
    for index, sample in enumerate(samples):
        signal = sample.get('governing_signal')
        if not isinstance(signal, dict) or not signal.get('native_actor_id'):
            raise ValueError('Governing Native signal actor absent')
        if signal.get('native_state') not in ('Green', 'TrafficLightState.Green',
                                              'Red', 'TrafficLightState.Red'):
            raise ValueError('Governing Native signal state not retained')
        if signal.get('authored_aspect') != 'green_straight_arrow':
            raise ValueError('Authored straight-arrow source absent')
        if signal.get('facing_ego_native_survey') is not True:
            raise ValueError('Governing head direction not surveyed')
        if signal.get('native_state') in ('Green', 'TrafficLightState.Green') and index in verified_arrow_frames:
            active.append(index)
        body = sample.get('native_body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Native body absent')
        front = max(v[1] for v in body)
        if prior_front is not None and prior_front < STOP_LINE_Y <= front:
            crossings.append(index)
        prior_front = front
        yaw = sample.get('native_yaw_deg')
        if not isinstance(yaw, (int, float)) or not math.isfinite(yaw):
            raise ValueError('Native heading absent')
        if initial_yaw is None:
            initial_yaw = yaw
        if abs((yaw - initial_yaw + 180) % 360 - 180) > 20:
            forbidden_turn.append(index)
        other = sample.get('other_vehicle')
        if not isinstance(other, dict) or not other.get('native_actor_id'):
            raise ValueError('Original other vehicle actor missing')
        vertices = other.get('native_body_xy_m')
        if not isinstance(vertices, list) or len(vertices) != 4:
            raise ValueError('Other vehicle Native body absent')
        within = overlap(vertices, INTERSECTION) > 0 or overlap(vertices, CROSSWALK) > 0
        if within:
            occupancies.append(index)
        if other.get('within_intersection_or_adjacent_crosswalk') is not within:
            raise ValueError('Other vehicle occupancy disagrees with Native footprint')
    if not active:
        raise ValueError('No verified sole green straight-arrow frame')
    if not crossings:
        raise ValueError('Ego stop-line crossing absent')
    crossing = crossings[0]
    occupied_at_arrow = [i for i in occupancies if i in active]
    clearance = max(occupied_at_arrow) if occupied_at_arrow else None
    lawful_occupied = [i for i in occupied_at_arrow
                       if samples[i]['other_vehicle'].get('prior_green_entry_observed') is True]
    speed_at_crossing = samples[crossing].get('speed_mps')
    if type(speed_at_crossing) not in (int, float) or not math.isfinite(speed_at_crossing):
        raise ValueError('Original speed missing at crossing')
    return {
        'sole_arrow_pixel_verified_frames': len(active),
        'first_front_stop_line_crossing_frame': crossing,
        'last_other_vehicle_occupancy_under_verified_arrow_frame': clearance,
        'other_vehicle_present_under_verified_arrow': bool(occupied_at_arrow),
        'prior_green_entry_within_verified_arrow': bool(lawful_occupied),
        'yielded_before_entry': clearance is None or crossing > clearance,
        'straight_heading_no_turn_observed': not forbidden_turn,
        'heading_deviation_frames': forbidden_turn,
        'other_vehicle_lawful_entry_inferred': False,
        'legal_verdict_claimed': False,
    }
