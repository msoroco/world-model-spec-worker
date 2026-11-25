"""Capture original CARLA trail traversal rows for the saved source audit.

The source packet binds administrative assertions; live location and sign-face
readback bind physical observations. No legal sufficiency or video claim follows.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from saved_audit import ASSIGNMENT_ID, audit_history
from source_packet import verify_packet
from trail import validate_source


def capture(world, vehicle, operator_id, sign_observer, site, case,
            packet_path, output, camera_plan_sha256, frame_count=900,
            before_tick=None, on_frame=None):
    validate_source(site, case)
    source = verify_packet(site, Path(packet_path))
    if type(frame_count) is not int or frame_count != 900:
        raise ValueError('full trail capture requires 900 frames')
    if not operator_id or not vehicle.id or not camera_plan_sha256:
        raise ValueError('operator, vehicle or camera plan identity missing')
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-9:
        raise ValueError('live world must be synchronous 20 Hz')
    if hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest() != site['map_sha256']:
        raise ValueError('live OpenDRIVE differs from reviewed trail')
    case_id = ASSIGNMENT_ID + '__' + case.name
    path = Path(output)
    packet_path_out = path.with_name(path.stem + '-packets.jsonl')
    if path.exists() or packet_path_out.exists():
        raise ValueError('refusing to overwrite original history or packets')
    route_sha = hashlib.sha256(json.dumps(site['route_xy'], separators=(',', ':')).encode()).hexdigest()
    box = site['corridor_box_xy']
    fixed = {
        'case_id': case_id, 'cell_id': 'C143687',
        'map_sha256': site['map_sha256'],
        'corridor_source_sha256': site['corridor_source_sha256'],
        'route_sha256': route_sha, 'vehicle_blueprint': site['vehicle_blueprint'],
        'operator_source_sha256': site['operator_source_sha256'],
        'camera_plan_sha256': camera_plan_sha256, 'duration_frames': frame_count,
        'official_plan_designation': case.designated,
        'city_trail_dedication': case.dedicated,
        'prohibits_motor_vehicles': case.prohibition_posted,
        'emergency_use': case.emergency_use,
        'maintenance_use': case.maintenance_use,
        'sign_face_sha256': site['sign']['face_readback_sha256'],
        'governed_access_sha256': site['sign']['governed_access_sha256'],
        'official_plan_source_sha256': source['source_sha256']['official_plan_designation'],
        'dedication_source_sha256': source['source_sha256']['city_trail_dedication'],
        'exception_status_source_sha256': source['source_sha256']['exception_status'],
        'vehicle_id': vehicle.id, 'operator_id': operator_id,
    }
    previous = None
    rows, packet_lines = [], []
    for _ in range(frame_count):
        if before_tick is not None:
            before_tick(vehicle, site, len(rows))
        tick_frame = world.tick()
        snapshot = world.get_snapshot()
        frame, time_s = snapshot.frame, float(snapshot.timestamp.elapsed_seconds)
        if type(frame) is not int or frame != tick_frame or not math.isfinite(time_s):
            raise ValueError('original frame or clock differs from tick')
        if previous is not None and (frame != previous[0] + 1 or
                                     not .049 <= time_s - previous[1] <= .051):
            raise ValueError('original frame/time is not contiguous 20 Hz')
        previous = frame, time_s
        location = vehicle.get_transform().location
        x, y = float(location.x), float(location.y)
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('nonfinite original vehicle location')
        sign_visible = sign_observer(snapshot, site['sign'])
        if type(sign_visible) is not bool:
            raise ValueError('live sign face readback missing')
        native_packet = {'frame': frame, 'time_s': time_s, 'vehicle_id': vehicle.id,
                         'location_xy': [x, y], 'sign_face_visible': sign_visible}
        packet_line = (json.dumps(native_packet, sort_keys=True, allow_nan=False) + '\n').encode()
        packet_lines.append(packet_line)
        packet_sha = hashlib.sha256(packet_line).hexdigest()
        rows.append({**fixed, 'original_frame': frame, 'time_s': time_s,
                     'vehicle_inside_corridor': box[0] <= x <= box[2] and box[1] <= y <= box[3],
                     'sign_face_visible': sign_visible,
                     'native_packet_sha256': packet_sha})
        if on_frame is not None:
            on_frame({'case_id': case_id, 'frame': frame, 'time_s': time_s,
                      'vehicle_id': vehicle.id, 'location_xy': [x, y]}, snapshot)
    raw = ''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows).encode()
    packet_path_out.write_bytes(b''.join(packet_lines))
    path.write_bytes(raw)
    digest = hashlib.sha256(raw).hexdigest()
    return audit_history(path, digest, case_id)
