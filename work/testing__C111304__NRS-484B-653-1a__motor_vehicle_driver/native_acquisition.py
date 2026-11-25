"""Adapter-driven Native encounter acquisition; no CARLA import at module load.

The local adapter must bind tick/read_actor/read_camera/brake/destroy to original
CARLA state. This records source packets, not a physical or legal acceptance.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

CAMERAS = ('front', 'rear', 'left', 'right')
ASSIGNMENT = 'testing__C111304__NRS-484B-653-1a__motor_vehicle_driver'


def _require(value, message):
    if not value:
        raise ValueError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _encoded(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _point(packet, label):
    xy = packet.get('xy')
    _require(isinstance(xy, list) and len(xy) == 2 and
             all(type(x) in (float, int) and math.isfinite(x) for x in xy), f'{label} xy missing')
    speed = packet.get('speed_mps')
    _require(type(speed) in (float, int) and math.isfinite(speed) and speed >= 0,
             f'{label} speed missing')
    _require(isinstance(packet.get('id'), (str, int)) and str(packet['id']), f'{label} id missing')
    return xy, speed


def capture(adapter, actors: dict, case, site: dict, output: Path, *, frames: int = 900,
            pipeline=None):
    """Capture original 20 Hz readbacks and four camera source hashes.

    adapter.tick() returns (original_frame, elapsed_seconds); read_actor returns
    current original state for ego/crossing/occupant/property. read_camera returns
    (original_frame, encoded_original_png_bytes) for each named camera. The caller owns the
    supplied adapter; this function brakes ego and destroys its constructed actors.
    """
    from encounter import CASES

    _require(case in CASES and actors.get('case_id') == case.case_id, 'case identity mismatch')
    _require(frames == 900, 'delivery requires 900 original frames')
    _require(_digest(site.get('site_sha256')) and _digest(site.get('map_sha256')) and
             _digest(site.get('camera_plan_sha256')), 'site/map/camera source missing')
    _require(site.get('public_access_basis') == case.public_access_basis, 'public access basis mismatch')
    _require(output.is_dir(), 'attempt output directory missing')
    prior = ('original-history.jsonl', 'original-packets.jsonl', 'original-cameras.jsonl',
             'video_frames.jsonl', 'native-receipt.json')
    _require(not any((output / name).exists() for name in
                 (prior if pipeline is not None else (*prior, 'trace.jsonl'))),
             'attempt output already exists')
    if pipeline is not None:
        _require((output / 'trace.jsonl').is_file() and not (output / 'trace.jsonl').is_symlink(),
                 'PipelineCapture original trace missing')
    histories = []
    packet_rows = []
    camera_rows = []
    first_frame = None
    first_time = None
    fixed_ids = None
    try:
        for index in range(frames):
            frame, elapsed = adapter.tick()
            _require(type(frame) is int and type(elapsed) in (float, int) and math.isfinite(elapsed),
                     'original tick identity missing')
            if first_frame is None:
                first_frame, first_time = frame, elapsed
            _require(frame == first_frame + index, 'original frame discontinuity')
            _require(abs(elapsed - (first_time + index / 20)) <= 0.001,
                     '20 Hz elapsed-time discontinuity')
            if pipeline is not None:
                pipeline.capture(frame, elapsed - first_time)
            packets = {role: adapter.read_actor(actors[role]) for role in
                       ('ego', 'crossing_vehicle', 'occupant', 'property')}
            for role, packet in packets.items():
                _require(isinstance(packet, dict), f'{role} original packet missing')
                _require(packet.get('original_frame') == frame, f'{role} frame join mismatch')
                _point(packet, role)
            ids = tuple(str(packets[role]['id']) for role in
                        ('ego', 'crossing_vehicle', 'occupant', 'property'))
            if fixed_ids is None:
                fixed_ids = ids
            _require(ids == fixed_ids, 'actor identity changed')
            _require(str(packets['occupant'].get('vehicle_id')) == ids[1], 'occupant vehicle join mismatch')
            controls = adapter.read_control(actors['ego'], actors['crossing_vehicle'])
            _require(isinstance(controls, dict) and controls.get('original_frame') == frame,
                     'original control packet missing')
            for key, expected in (('ego_target_speed_mps', case.ego_speed_mps),
                                  ('crossing_target_speed_mps', case.crossing_speed_mps),
                                  ('crossing_release_s', case.crossing_release_s)):
                _require(controls.get(key) == expected, f'original {key} differs from exact case')
            source = {'actors': packets, 'control': controls, 'original_frame': frame}
            row = {
                'case_id': f'{ASSIGNMENT}__{case.case_id}',
                'original_frame': frame, 'elapsed_seconds': elapsed,
                'source_sha256': _sha(_encoded(source)),
                'control_command_source_sha256': _sha(_encoded(controls)),
                'map_source_sha256': site['map_sha256'], 'map_sha256': site['map_sha256'],
                'site_sha256': site['site_sha256'],
                'camera_plan_sha256': site['camera_plan_sha256'],
                'public_access_basis': case.public_access_basis,
                'ego_id': ids[0], 'crossing_vehicle_id': ids[1],
                'occupant_id': ids[2], 'property_id': ids[3],
                'occupant_vehicle_id': ids[1],
                'ego_blueprint': packets['ego'].get('blueprint'),
                'crossing_blueprint': packets['crossing_vehicle'].get('blueprint'),
                'property_blueprint': packets['property'].get('blueprint'),
                'ego_xy': packets['ego']['xy'], 'occupant_xy': packets['occupant']['xy'],
                'property_xy': packets['property']['xy'],
                'ego_speed_mps': packets['ego']['speed_mps'],
                'crossing_speed_mps': packets['crossing_vehicle']['speed_mps'],
            }
            _require(all(row[key] for key in ('ego_blueprint', 'crossing_blueprint', 'property_blueprint')),
                     'actor blueprint missing')
            histories.append(row)
            packet_rows.append(source)
            cameras = {}
            for camera in CAMERAS:
                camera_frame, raw = adapter.read_camera(camera)
                _require(camera_frame == frame and isinstance(raw, bytes) and raw,
                         f'{camera} original camera frame missing')
                cameras[camera] = _sha(raw)
            camera_rows.append({'original_frame': frame, 'camera_sha256': cameras})
        _require(any(row['ego_speed_mps'] > 0 for row in histories[1:]),
                 'ego never moved in original acquisition')
        _require(any(row['crossing_speed_mps'] > 0 for row in histories[1:]),
                 'crossing vehicle never moved in original acquisition')
        if pipeline is not None:
            pipeline.close(confirmed=True)
        encoded_history = b''.join(_encoded(row) + b'\n' for row in histories)
        encoded_packets = b''.join(_encoded(row) + b'\n' for row in packet_rows)
        encoded_cameras = b''.join(_encoded(row) + b'\n' for row in camera_rows)
        trace_rows = []
        frame_map_rows = []
        for index, (row, packet) in enumerate(zip(histories, packet_rows)):
            ego = packet['actors']['ego']
            z, heading = ego.get('z'), ego.get('heading_deg')
            _require(type(z) in (int, float) and math.isfinite(z) and
                     type(heading) in (int, float) and math.isfinite(heading),
                     'original ego height or heading missing')
            elapsed = row['elapsed_seconds'] - first_time
            trace_rows.append({'frame': row['original_frame'], 'time_s': elapsed,
                               'position_m': [*ego['xy'], z],
                               'position': {'x': ego['xy'][0], 'y': ego['xy'][1], 'z': z},
                               'heading_deg': heading, 'speed_mps': ego['speed_mps'],
                               'speed_mph': ego['speed_mps'] / .44704})
            frame_map_rows.append({'video_frame': index, 'carla_frame': row['original_frame'],
                                   'time_s': elapsed})
        encoded_trace = ((output / 'trace.jsonl').read_bytes() if pipeline is not None
                         else b''.join(_encoded(row) + b'\n' for row in trace_rows))
        if pipeline is not None:
            actual_trace = [json.loads(line) for line in encoded_trace.decode('utf-8').splitlines()]
            _require(len(actual_trace) == frames and all(
                all(actual.get(key) == expected for key, expected in row.items())
                for actual, row in zip(actual_trace, trace_rows)),
                'PipelineCapture trace differs from original actor readback')
        encoded_map = b''.join(_encoded(row) + b'\n' for row in frame_map_rows)
        receipt = {'format': 'worker-native-encounter-acquisition',
                   'assignment_id': ASSIGNMENT, 'case_id': f'{ASSIGNMENT}__{case.case_id}',
                   'site_sha256': site['site_sha256'], 'map_sha256': site['map_sha256'],
                   'camera_plan_sha256': site['camera_plan_sha256'],
                   'public_access_basis': case.public_access_basis,
                   'ego_target_speed_mps': case.ego_speed_mps,
                   'crossing_target_speed_mps': case.crossing_speed_mps,
                   'crossing_release_s': case.crossing_release_s,
                   'first_original_frame': first_frame, 'last_original_frame': first_frame + frames - 1,
                   'frame_count': frames, 'original_fps': 20,
                   'original_history_sha256': _sha(encoded_history),
                   'original_packets_sha256': _sha(encoded_packets),
                   'original_cameras_sha256': _sha(encoded_cameras),
                   'original_trace_sha256': _sha(encoded_trace),
                   'original_frame_map_sha256': _sha(encoded_map),
                   'physical_visibility_verified': False, 'legal_judgment': None}
        for name, data in (('original-history.jsonl', encoded_history),
                           ('original-packets.jsonl', encoded_packets),
                           ('original-cameras.jsonl', encoded_cameras),
                           ('video_frames.jsonl', encoded_map),
                           ('native-receipt.json', _encoded(receipt) + b'\n')):
            tmp = output / (name + '.tmp')
            tmp.write_bytes(data)
            os.replace(tmp, output / name)
        if pipeline is None:
            (output / 'trace.jsonl').write_bytes(encoded_trace)
        return receipt
    finally:
        try:
            if pipeline is not None and not pipeline.closed:
                pipeline.close(confirmed=False)
            adapter.brake(actors['ego'])
        finally:
            for actor in reversed(actors['owned']):
                adapter.destroy(actor)
