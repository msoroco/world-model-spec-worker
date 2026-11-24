"""Record exact original-frame crosswalk observations and camera PNGs.

The adapter owns CARLA resources. This module requires readbacks and original PNG
pixels for every tick and always calls brake and cleanup. It creates no diagnostic evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from crosswalk import SourceError, construct, measure, require, sealed_json

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERA_SIZES = {'overview': (1920, 1080), 'approach': (1280, 720),
                'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def _write_sealed(root: Path, name: str, value: object) -> dict:
    raw = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path = root / name
    path.write_bytes(raw)
    return {'path': name, 'sha256': hashlib.sha256(raw).hexdigest()}


def capture(adapter, site_ref: dict, vehicle_ref: dict, case: dict,
            source_root: Path, output_root: Path, frame_count: int = 900,
            exception_ref: dict | None = None) -> dict:
    """Use adapter.tick/read_subject/read_cameras; require original 20 Hz identity.

    A Native adapter must return real simulator frame/time and actual actor and
    camera readbacks. The source site and vehicle are SHA-bound inputs.
    """
    require(frame_count == 900, 'exact delivery requires 900 frames')
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    site = sealed_json(site_ref, source_root)
    if case['exception'] != 'none':
        require(exception_ref is not None, 'exact exception source missing')
        packet = sealed_json(exception_ref, source_root)
        require(packet.get('kind') == case['exception'], 'exact exception source kind differs')
        require(packet.get('instruction_source') and packet.get('review_source'),
                'exception instruction and review sources missing')
        sealed_json(packet['instruction_source'], source_root)
        sealed_json(packet['review_source'], source_root)
        require(packet.get('source_sha256') == packet['instruction_source']['sha256'] and
                packet.get('reviewed_instruction_sha256') == packet['review_source']['sha256'],
                'exception nested source hash mismatch')
    else:
        require(exception_ref is None, 'unexpected exception source')
    subject = None
    rows, frame_map, camera_map = [], [], {name: [] for name in CAMERAS}
    try:
        built = construct(adapter, site_ref, vehicle_ref, case, source_root)
        subject = built['subject_id']
        for index in range(frame_count):
            tick = adapter.tick()
            frame = tick['frame']
            time_s = tick['time_s']
            require(type(frame) is int and math.isfinite(time_s), 'Native frame identity missing')
            require(index == 0 or frame == rows[-1]['frame'] + 1, 'Native frame gap')
            require(index == 0 or abs(time_s - rows[-1]['time_s'] - 0.05) <= 0.001, 'Native cadence mismatch')
            body = adapter.read_subject(subject, frame)
            require(body['frame'] == frame and body['subject_id'] == subject, 'Native body identity mismatch')
            require(body['case_id'] == case['case_id'], 'Native body case mismatch')
            row = {**body, 'frame': frame, 'time_s': time_s}
            rows.append(row)
            frame_map.append({'frame': frame, 'time_s': time_s})
            cameras = adapter.read_cameras(frame)
            require(set(cameras) == set(CAMERAS), 'Native four-camera readback missing')
            for name in CAMERAS:
                readback = cameras[name]
                require(readback['frame'] == frame and readback['source_id'], 'Native camera frame mismatch')
                png = readback.get('png_bytes')
                require(isinstance(png, bytes) and png.startswith(b'\x89PNG\r\n\x1a\n'),
                        'Native camera PNG pixels missing')
                media_dir = output_root / 'camera-sources' / name
                media_dir.mkdir(parents=True, exist_ok=True)
                media_path = media_dir / f'{index:04d}.png'
                media_path.write_bytes(png)
                camera_map[name].append({'frame': frame, 'source_id': readback['source_id'],
                                         'path': str(media_path.relative_to(output_root)),
                                         'sha256': hashlib.sha256(png).hexdigest()})
        expected = {'case_id': case['case_id'], 'subject_id': subject,
                    'first_frame': rows[0]['frame'], 'frame_count': frame_count,
                    'crosswalk_id': site['crosswalk_id'], 'marking_status': site['marking_status'],
                    'crosswalk_polygon': site['crosswalk_polygon'], 'action': case['action'],
                    'exception': case['exception']}
        measurement = measure(rows, expected)
        refs = {'actor_rows': _write_sealed(output_root, 'actor-rows.json', rows),
                'frame_map': _write_sealed(output_root, 'frame-map.json', frame_map),
                'camera_readbacks': _write_sealed(output_root, 'camera-readbacks.json', camera_map)}
        receipt = {'format': 'crosswalk-native-source-receipt', 'case_id': case['case_id'],
                   'subject_id': subject, 'fps': 20, 'frame_count': frame_count,
                   'source_format': 'native_original', 'site_source': site_ref,
                   'vehicle_source': vehicle_ref, 'exception_source': exception_ref,
                   'sources': refs, 'measurement': measurement,
                   'camera_source_format': 'png_original', 'video_decode': 'not_run',
                   'physical_acceptance': 'unreviewed'}
        _write_sealed(output_root, 'native-receipt.json', receipt)
        return receipt
    finally:
        try:
            if subject is not None:
                adapter.brake(subject)
        finally:
            adapter.cleanup()
