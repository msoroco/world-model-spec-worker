"""Lazy Native acquisition of the center-lane turn and merge observation.

The local runner supplies original world/sample/camera readbacks. This module
never infers an event from a commanded route or a planned distance.
"""

import hashlib
import importlib.util
import json
from math import isfinite
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location('center_lane_site_for_capture', _ROOT / 'center_lane_site.py')
_SITE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SITE)
_SPEC = importlib.util.spec_from_file_location('center_lane_measurement_for_capture', _ROOT / 'center_lane_measurement.py')
_MEASUREMENT = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MEASUREMENT)
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERA_DIMENSIONS = {'overview': (1920, 1080), 'approach': (1280, 720),
                     'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sensor_frame_reader(attempt_root, original_reader, dimensions=None):
    """Save synchronized original BGRA sensor readbacks as four lossless PNGs.

    The wrapped reader supplies ``camera_images`` keyed by view. Each image has
    Native frame, width, height and raw_data attributes. Dimensions may be
    overridden only for CPU fixtures; local acquisition uses the profile above.
    The returned reader feeds ``capture_original`` without a CARLA import.
    """
    from PIL import Image

    root = Path(attempt_root).resolve()
    expected = CAMERA_DIMENSIONS if dimensions is None else dimensions
    if not isinstance(expected, dict) or set(expected) != set(VIEWS):
        raise ValueError('incomplete four-camera dimensions')
    if any(not isinstance(expected[view], (list, tuple)) or len(expected[view]) != 2 or
           any(type(value) is not int or value <= 0 for value in expected[view]) for view in VIEWS):
        raise ValueError('invalid camera dimensions')

    def read(index):
        row = original_reader(index)
        if not isinstance(row, dict):
            raise ValueError('missing original frame readback')
        frame = row.get('frame')
        images = row.get('camera_images')
        if type(frame) is not int or not isinstance(images, dict) or set(images) != set(VIEWS):
            raise ValueError('incomplete synchronized camera sensor readback')
        sources = {}
        prepared = []
        for view in VIEWS:
            image = images[view]
            width, height = expected[view]
            if (getattr(image, 'frame', None) != frame or
                    getattr(image, 'width', None) != width or getattr(image, 'height', None) != height):
                raise ValueError('camera frame identity or dimensions mismatch: ' + view)
            raw = getattr(image, 'raw_data', None)
            if not isinstance(raw, (bytes, bytearray)) or len(raw) != width * height * 4:
                raise ValueError('incomplete original BGRA camera bytes: ' + view)
            relative = 'camera/' + view + '/%06d.png' % frame
            path = root / relative
            if path.exists():
                raise ValueError('original camera frame already exists: ' + relative)
            rgb = Image.frombytes('RGBA', (width, height), bytes(raw), 'raw', 'BGRA').convert('RGB')
            prepared.append((path, rgb))
            sources[view] = relative
        for path, rgb in prepared:
            path.parent.mkdir(parents=True, exist_ok=True)
            rgb.save(path, format='PNG')
        returned = dict(row)
        returned.pop('camera_images')
        returned['camera_sources'] = sources
        return returned

    return read


def _write_json(root, relative, value):
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('original capture source already exists: ' + relative)
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    target.write_bytes(raw)
    return {'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}


def _bound_source(root, binding):
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}:
        raise ValueError('missing exact source binding')
    relative = binding['path']
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or '..' in Path(relative).parts:
        raise ValueError('source path escapes attempt')
    source = (root / relative).resolve()
    if not source.is_relative_to(root.resolve()) or not source.is_file():
        raise ValueError('missing original source: ' + relative)
    if hashlib.sha256(source.read_bytes()).hexdigest() != binding['sha256']:
        raise ValueError('source hash mismatch: ' + relative)


def capture_original(attempt_root, case_id, site_packet, frame_reader, count, *, first_frame=None):
    """Persist exact original 20 Hz readbacks and a sealed measurement receipt.

    frame_reader(index) must return original frame, elapsed_seconds, body XY,
    lane_id, turn_complete, merged_into_through_lane, and four camera source
    paths. The caller owns ticking, sensor synchronization and world cleanup.
    """
    root = Path(attempt_root).resolve()
    if not isinstance(case_id, str) or not case_id or type(count) is not int or count < 3:
        raise ValueError('missing exact case or frame count')
    site = _SITE.validate_site(site_packet)
    for binding in (site['native_map_source'], site['highway_review_source']):
        _bound_source(root, binding)
    for relative in ('native/trace.json', 'native/frame_map.json', 'native/capture-receipt.json', 'native/site-packet.json'):
        if (root / relative).exists():
            raise ValueError('original capture source already exists: ' + relative)
    samples, mappings = [], []
    turn_count = 0
    previous_frame = None
    for index in range(count):
        reading = frame_reader(index)
        if not isinstance(reading, dict):
            raise ValueError('missing original frame readback')
        frame = reading.get('frame')
        if type(frame) is not int or (previous_frame is not None and frame != previous_frame + 1) or (index == 0 and first_frame is not None and frame != first_frame):
            raise ValueError('noncontiguous original frame identity')
        previous_frame = frame
        elapsed = reading.get('elapsed_seconds')
        if not isinstance(elapsed, (int, float)) or not isfinite(elapsed) or abs(elapsed - index / 20) > 0.001:
            raise ValueError('original frame is not synchronized at 20 Hz')
        lane_id = reading.get('lane_id')
        lane = {site['center_lane_id']: 'shared_center_turn', site['receiving_lane_id']: 'receiving_through', site['opposing_lane_id']: 'opposing_through'}.get(lane_id)
        if lane is None:
            lane = 'approach' if reading.get('approach_lane') is True else None
        if lane is None:
            raise ValueError('original lane identity is outside verified site')
        xy = reading.get('body_centre_xy_m')
        if not isinstance(xy, (list, tuple)) or len(xy) != 2 or any(not isinstance(v, (int, float)) or not isfinite(v) for v in xy):
            raise ValueError('missing original body centre')
        receiving_id = reading.get('receiving_vehicle_actor_id')
        if receiving_id is not None and (type(receiving_id) is not int or receiving_id <= 0):
            raise ValueError('receiving traffic actor identity invalid')
        turn = reading.get('left_turn_onto_highway_complete') is True
        merge = reading.get('merged_into_through_lane') is True
        if turn and lane != 'shared_center_turn':
            raise ValueError('turn completion marker outside shared center lane')
        if merge and lane != 'receiving_through':
            raise ValueError('merge marker outside receiving through lane')
        turn_count += int(turn)
        cameras = reading.get('camera_sources')
        if not isinstance(cameras, dict) or set(cameras) != set(VIEWS) or not all(isinstance(cameras[v], str) and cameras[v] for v in VIEWS):
            raise ValueError('incomplete original four-camera readback')
        camera_hashes = {}
        for view, relative in cameras.items():
            if Path(relative).is_absolute() or '..' in Path(relative).parts or relative.startswith('./'):
                raise ValueError('camera source path escapes attempt')
            camera_file = (root / relative).resolve()
            if not camera_file.is_relative_to(root) or not camera_file.is_file():
                raise ValueError('missing original camera source')
            camera_hashes[view] = hashlib.sha256(camera_file.read_bytes()).hexdigest()
        sample = {'frame': frame, 'elapsed_seconds': elapsed, 'body_centre_xy_m': list(xy), 'lane': lane,
                  'lane_id': lane_id, 'left_turn_onto_highway_complete': turn, 'merged_into_through_lane': merge}
        if receiving_id is not None:
            sample['receiving_vehicle_actor_id'] = receiving_id
        samples.append(sample)
        mappings.append({'frame': frame, 'camera_sources': cameras, 'camera_sha256': camera_hashes})
    if turn_count != 1:
        raise ValueError('exactly one observed turn completion required')
    trace = {'source': {'path': 'native/trace.json'}, 'highway_context_source': site['highway_review_source'],
             'lane_design_source': site['native_map_source'],
             'lane_design': 'single_shared_bidirectional_center_turn_only', 'samples': samples}
    measured = _MEASUREMENT.measure_center_lane_distance(trace)
    trace_source = _write_json(root, 'native/trace.json', trace)
    frame_map_source = _write_json(root, 'native/frame_map.json', {'fps': 20, 'frames': mappings})
    receipt = {'case_id': case_id, 'attempt_id': root.name, 'original_trace': trace_source,
               'highway_context_source': site['highway_review_source'], 'lane_design_source': site['native_map_source'],
               'frame_map_source': frame_map_source, 'delivered_measurement': measured,
               'site_source': _write_json(root, 'native/site-packet.json', site_packet)}
    _write_json(root, 'native/capture-receipt.json', receipt)
    return receipt
