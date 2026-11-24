"""Measure pedestrian highway entry against source-bound arrow and permission rows."""
import hashlib
import json
import math
from pathlib import Path

SOURCES = ('map.json', 'device.json', 'frames.jsonl')
FRAMES = 600
RATE_HZ = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def measure(folder):
    folder = Path(folder)
    manifest = read(folder / 'source-manifest.json')
    require(manifest.get('format') == 'c111334-entry-sources-v1', 'source manifest format')
    require(manifest.get('sha256') == {name: sha(folder / name) for name in SOURCES},
            'source hash mismatch')
    geometry = read(folder / 'map.json')
    device = read(folder / 'device.json')
    require(geometry.get('highway_y_min_m') == -3.0 and
            geometry.get('highway_y_max_m') == 3.0 and
            geometry.get('pedestrian_route_x_m') == 0.0, 'fixed highway geometry')
    require(device.get('vehicle_head_id') == 'turn-arrow-1' and
            device.get('pedestrian_device_id') == 'ped-head-1' and
            device.get('head_faces_subject') is True and
            device.get('permission_faces_subject') is True,
            'device facing or identity')
    rows = [json.loads(line) for line in (folder / 'frames.jsonl').read_text().splitlines()]
    require(len(rows) == FRAMES, '600 source frames required')
    first_entry = first_permission = None
    permission_at_first_entry = None
    entry_frames = arrow_frames = permission_frames = 0
    previous_y = None
    for i, row in enumerate(rows):
        require(row.get('frame') == i and row.get('native_frame') == 1000+i and
                type(row.get('time_s')) in (float, int) and
                abs(row['time_s'] - i/RATE_HZ) < 1e-9 and
                row.get('actor_id') == 101 and row.get('actor_kind') == 'pedestrian' and
                row.get('vehicle_head_id') == device['vehicle_head_id'] and
                row.get('pedestrian_device_id') == device['pedestrian_device_id'],
                f'frame/time/identity join {i}')
        body = row.get('body_polygon_xy_m')
        require(type(body) is list and len(body) == 4 and
                all(type(p) is list and len(p) == 2 and
                    all(type(v) in (float, int) and math.isfinite(v) for v in p)
                    for p in body), f'pedestrian body {i}')
        xs, ys = [p[0] for p in body], [p[1] for p in body]
        require(max(xs)-min(xs) >= .3 and max(xs)-min(xs) <= 1.2 and
                max(ys)-min(ys) >= .3 and max(ys)-min(ys) <= 1.2 and
                abs((max(xs)+min(xs))/2-geometry['pedestrian_route_x_m']) < .1,
                f'pedestrian body geometry {i}')
        center_y = (max(ys)+min(ys))/2
        require(previous_y is None or abs(center_y-previous_y) <= .15,
                f'pedestrian position continuity {i}')
        previous_y = center_y
        require(row.get('green_turn_arrow_alone') is True,
                f'green turn arrow alone not evidenced {i}')
        require(type(row.get('other_device_permits_proceed')) is bool,
                f'other device permission source {i}')
        arrow_frames += 1
        if row['other_device_permits_proceed']:
            permission_frames += 1
            if first_permission is None:
                first_permission = i
        occupying = min(ys) <= geometry['highway_y_max_m'] and max(ys) >= geometry['highway_y_min_m']
        if occupying:
            entry_frames += 1
            if first_entry is None:
                first_entry = i
                permission_at_first_entry = row['other_device_permits_proceed']
    before_permission = first_entry is not None and (
        permission_at_first_entry is not True)
    return {'format': 'c111334-entry-measurement-v1',
            'first_highway_entry_frame': first_entry,
            'first_other_device_permission_frame': first_permission,
            'other_device_permission_at_first_entry': permission_at_first_entry,
            'entry_before_permission': before_permission,
            'highway_occupancy_frames': entry_frames,
            'arrow_alone_facing_frames': arrow_frames,
            'other_device_permission_frames': permission_frames,
            'frames': FRAMES, 'rate_hz': RATE_HZ,
            'source_sha256': manifest['sha256'],
            'legal_verdict_claimed': False, 'original_native_observed': False}
