"""Bind an explicit Native-source review to retained C228133 frame rows.

The review is an operator observation, never inferred from a requested CARLA
light state. This module checks its provenance and produces measurement rows.
"""

import hashlib
import json
from pathlib import Path

from source_capture import VIEWS


def _digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines()]
    if not rows or [row.get('frame') for row in rows] != list(range(len(rows))):
        raise ValueError('Review source frames must be continuous')
    return rows


def bind(attempt, review, diagnostic_fixture=False):
    attempt, review = Path(attempt), Path(review)
    data = json.loads(review.read_text())
    names = ('native-signal-frames.jsonl',
             'native-pedestrian-device-frames.jsonl', 'video_frames.jsonl',
             'road-boundary.json', 'governing-device-authority.json',
             'highway-authority.json')
    sources = data.get('source_sha256')
    if data.get('format') != 'c228133-native-source-review-v1' or \
            not isinstance(data.get('reviewer'), str) or not data['reviewer'].strip() or \
            not isinstance(sources, dict) or set(sources) != set(names):
        raise ValueError('Incomplete named Native source review')
    for name in names:
        if _digest(attempt / name) != sources[name]:
            raise ValueError('Reviewed Native source changed: ' + name)
    geometry = json.loads((attempt / 'road-boundary.json').read_text())
    governing = json.loads((attempt / 'governing-device-authority.json').read_text())
    highway = json.loads((attempt / 'highway-authority.json').read_text())
    if geometry.get('source_kind') != ('synthetic_native_sample' if diagnostic_fixture
                                      else 'native_map_readback') or \
            data.get('highway_boundary_reviewed') is not True or \
            data.get('highway_boundary_basis') not in (
                ('synthetic_cpu_fixture',) if diagnostic_fixture else
                ('dedication_and_public_use', 'official_road_inventory')) or \
            highway.get('format') != 'c228133-highway-authority-v1' or \
            highway.get('source_kind') != ('synthetic_cpu_fixture' if diagnostic_fixture
                                           else 'independent_highway_authority') or \
            highway.get('basis') != data.get('highway_boundary_basis') or \
            highway.get('native_road_id') != geometry.get('native_road_id') or \
            highway.get('boundary_y_m') != geometry.get('boundary_y_m') or \
            highway.get('road_side') != geometry.get('road_side') or \
            not isinstance(highway.get('authority_reference'), str) or \
            not highway['authority_reference'].strip():
        raise ValueError('Highway boundary requires independent source review')
    if governing.get('format') != 'c228133-governing-device-authority-v1' or \
            governing.get('source_kind') != ('synthetic_cpu_fixture' if diagnostic_fixture
                                             else 'official_traffic_control_inventory') or \
            (not diagnostic_fixture and governing.get('is_debug_geometry') is not False) or \
            not isinstance(governing.get('authority_reference'), str) or \
            not governing['authority_reference'].strip() or \
            governing.get('red_actor_id') == governing.get('arrow_actor_id'):
        raise ValueError('Official governing signal authority missing')
    signal_rows = _rows(attempt / names[0])
    device_rows = _rows(attempt / names[1])
    footage = [json.loads(line) for line in (attempt / names[2]).read_text().splitlines()]
    decisions = data.get('frames')
    if not isinstance(decisions, list) or len(decisions) != len(signal_rows) or \
            len(device_rows) != len(signal_rows) or len(footage) != len(signal_rows):
        raise ValueError('Review must cover every synchronized Native frame')
    reviewed_signals, reviewed_devices = [], []
    for index, (signal, device, video, decision) in enumerate(zip(
            signal_rows, device_rows, footage, decisions)):
        if not isinstance(decision, dict) or decision.get('frame') != index or \
                video.get('video_frame') != index or \
                any(row.get('native_frame') != video.get('native_frame')
                    for row in (signal, device)):
            raise ValueError('Reviewed frame identity mismatch')
        hashes = video.get('source_rgb_sha256')
        if not isinstance(hashes, dict) or set(hashes) != set(VIEWS) or \
                decision.get('source_rgb_sha256') != hashes:
            raise ValueError('Review does not bind four original camera frames')
        if signal.get('red_actor_id') == signal.get('arrow_actor_id') or \
                decision.get('red_actor_id') != signal.get('red_actor_id') or \
                decision.get('arrow_actor_id') != signal.get('arrow_actor_id') or \
                signal.get('red_actor_id') != governing.get('red_actor_id') or \
                signal.get('arrow_actor_id') != governing.get('arrow_actor_id') or \
                decision.get('device_actor_id') != device.get('device_actor_id'):
            raise ValueError('Review actor identity mismatch')
        if decision.get('red') not in ('steady', 'other') or \
                type(decision.get('green_turn_arrow')) is not bool or \
                type(decision.get('governs_pedestrian')) is not bool or \
                type(decision.get('permits_proceed')) is not bool or \
                decision.get('directional_arrow_pixels_reviewed') is not True or \
                decision.get('facing_governance_reviewed') is not True or \
                decision.get('other_device_inventory_reviewed') is not True:
            raise ValueError('Missing explicit signal, facing, or exception review')
        if decision['red'] == 'steady' and signal.get('observed_red_actor_state') != 'Red':
            raise ValueError('Steady red contradicts Native actor state')
        if decision['green_turn_arrow'] and signal.get('observed_arrow_actor_state') != 'Green':
            raise ValueError('Green arrow contradicts Native actor state')
        if decision['permits_proceed'] and device.get('device_actor_id') is None:
            raise ValueError('Permission requires an identified other device')
        signal = dict(signal)
        signal.update(red=decision['red'],
                      green_turn_arrow=decision['green_turn_arrow'],
                      governs_pedestrian=decision['governs_pedestrian'],
                      directional_arrow_pixels_verified=True,
                      facing_governance_verified=True)
        device = dict(device)
        device.update(permits_proceed=decision['permits_proceed'],
                      permission_reviewed=True)
        reviewed_signals.append(signal)
        reviewed_devices.append(device)
    return reviewed_signals, reviewed_devices


def write_bound_rows(attempt, review, output, diagnostic_fixture=False):
    signals, devices = bind(attempt, review, diagnostic_fixture)
    output = Path(output)
    if output.exists():
        raise ValueError('Retain prior review output; use a new directory')
    output.mkdir(parents=True)
    for name, rows in (('native-signal-frames.jsonl', signals),
                       ('native-pedestrian-device-frames.jsonl', devices)):
        (output / name).write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                           for row in rows))
    return len(signals)
