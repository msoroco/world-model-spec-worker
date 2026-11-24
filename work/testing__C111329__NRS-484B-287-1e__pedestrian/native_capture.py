"""Acquire original diagonal walker and governing-device readback at 20 Hz."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from diagonal_crossing import validate_site
from saved_crossing import ASSIGNMENT, CAMERAS, CASE_STATES, process_saved


def _seal_json(root, name, value):
    path = root / name
    data = (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()
    path.write_bytes(data)
    return {'path': name, 'sha256': hashlib.sha256(data).hexdigest()}


def _local_site(site, attempt):
    copied = dict(site)
    copied['sources'] = {}
    for name, ref in site['sources'].items():
        original = Path(ref['path'])
        if not original.is_file() or hashlib.sha256(original.read_bytes()).hexdigest() != ref['sha256']:
            raise ValueError('reviewed site source hash mismatch: ' + name)
        target = attempt / ('original-' + name + original.suffix)
        if target.exists():
            raise ValueError('original site source already exists')
        target.write_bytes(original.read_bytes())
        copied['sources'][name] = {'path': target.name, 'sha256': ref['sha256']}
    validate_site(copied, attempt)
    return copied


def capture(world, site, case_id, attempt, walker_reader, device_reader,
            camera_frame_reader, crossing_polygon, *, diagnostic=True,
            attest_original=False):
    """Read exactly 900 synchronous ticks; callbacks return new-frame facts."""
    if case_id not in CASE_STATES:
        raise ValueError('unassigned diagonal case')
    if not diagnostic and not attest_original:
        raise ValueError('reviewed original Native adapter attestation required')
    validate_site(site)
    attempt = Path(attempt).resolve()
    if not attempt.is_dir() or any(attempt.iterdir()):
        raise ValueError('fresh materialized attempt required')
    if not all(callable(fn) for fn in (walker_reader, device_reader, camera_frame_reader)):
        raise ValueError('original Native readers required')
    local_site = _local_site(site, attempt)
    rows = {'walker': [], 'device': [], 'camera_frames': []}
    previous = None
    start_time = None
    for index in range(900):
        tick = world.tick()
        snapshot = world.get_snapshot()
        frame = snapshot.frame
        time_s = snapshot.timestamp.elapsed_seconds
        if type(frame) is not int or frame != tick or (previous is not None and frame != previous + 1):
            raise ValueError('original Native frame discontinuity')
        if not isinstance(time_s, (int, float)) or not math.isfinite(time_s):
            raise ValueError('original Native timestamp missing')
        if start_time is None:
            start_time = time_s
        if abs(time_s - start_time - index / 20) > .001:
            raise ValueError('original Native 20 Hz drift')
        stamp = {'original_frame': frame, 'elapsed_s': index / 20}
        walker = walker_reader(snapshot)
        device = device_reader(snapshot, local_site['governing_device']['id'])
        cameras = camera_frame_reader(snapshot)
        if not isinstance(walker, dict) or walker.get('source_kind') != 'native_walker_readback':
            raise ValueError('original Native walker readback required')
        if not isinstance(device, dict) or device.get('source_kind') != 'native_device_readback':
            raise ValueError('original Native device readback required')
        if not isinstance(cameras, dict) or set(cameras) != set(CAMERAS) or any(
                type(cameras[name]) is not int or cameras[name] != frame for name in CAMERAS):
            raise ValueError('four original camera frame readbacks required')
        if walker.get('original_frame') != frame or device.get('original_frame') != frame:
            raise ValueError('walker/device original frame differs')
        if device.get('device_id') != local_site['governing_device']['id']:
            raise ValueError('governing diagonal device differs')
        if device.get('source_sha256') != local_site['sources']['device_inventory']['sha256']:
            raise ValueError('device inventory source differs')
        rows['walker'].append({**stamp, 'walker_id': walker['walker_id'],
                               'center_xy': walker['center_xy']})
        rows['device'].append({**stamp, 'device_id': device['device_id'],
                               'source_sha256': device['source_sha256'],
                               'pedestrian_governance': device['pedestrian_governance'],
                               'instruction': device['instruction']})
        rows['camera_frames'].append({**stamp, 'cameras': cameras.copy()})
        previous = frame
    refs = {'site': _seal_json(attempt, 'site.json', local_site),
            'walker': _seal_json(attempt, 'walker.json', rows['walker']),
            'device': _seal_json(attempt, 'device.json', rows['device']),
            'camera_frames': _seal_json(attempt, 'camera-frames.json', rows['camera_frames']),
            'crossing_polygon': _seal_json(attempt, 'crossing-polygon.json', crossing_polygon)}
    acquisition = {'assignment_id': ASSIGNMENT, 'case_id': case_id,
                   'diagnostic': diagnostic, 'fps': 20,
                   'camera_ids': list(CAMERAS), **refs,
                   'capture_origin': 'native_adapter_attested' if attest_original else 'diagnostic_adapter',
                   'camera_media_status': 'not_acquired_by_frame_reader'}
    # Publish only after the saved analyzer verifies all original sources.
    path = attempt / 'acquisition.json'
    path.write_text(json.dumps(acquisition, sort_keys=True, indent=2) + '\n')
    try:
        result = process_saved(attempt, case_id, attempt / 'measurement.json',
                               allow_diagnostic=diagnostic)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return {'acquisition': acquisition, 'measurement': result}
