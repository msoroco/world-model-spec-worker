"""Native 20 Hz crossing capture using injected CARLA-facing adapters.

The site and reader bindings are original sources. This module captures what
occurred; it never fills a missing signal or device observation from the plan.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile, ZIP_STORED

from PIL import Image

from native_crossing import SourceError, require, verify_site, inside
from pedestrian_control import RouteFollower, ENTER_CASES, WAIT_CASES

ASSIGNMENT = 'testing__C111125__NRS-484B-307-2b__pedestrian'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERA_DIMENSIONS = {'overview': (1920, 1080),
                     'approach': (1280, 720),
                     'reference_corner': (1280, 720),
                     'driver_reference': (1280, 720)}


def _image_bytes(reader, frame, dimensions):
    sample = reader(frame)
    require(isinstance(sample, dict) and sample.get('frame') == frame,
            'camera frame identity mismatch')
    payload = sample.get('png_bytes')
    require(isinstance(payload, bytes) and payload.startswith(b'\x89PNG\r\n\x1a\n'),
            'camera PNG source missing')
    with Image.open(BytesIO(payload)) as image:
        image.verify()
    with Image.open(BytesIO(payload)) as image:
        require(image.format == 'PNG' and image.size == dimensions,
                'camera PNG format or dimensions mismatch')
        image.load()
    return payload


def _frame(world, actor, site, head_reader, device_reader):
    snapshot = world.get_snapshot()
    frame = snapshot.frame
    elapsed = snapshot.timestamp.elapsed_seconds
    require(isinstance(frame, int) and frame >= 0, 'missing native frame identity')
    require(isinstance(elapsed, (float, int)) and math.isfinite(elapsed), 'missing native time')
    head = head_reader(site['official_signal_head_id'])
    device = device_reader(site['other_device_id'])
    require(head['head_id'] == site['official_signal_head_id'], 'observed signal head mismatch')
    require(device['device_id'] == site['other_device_id'], 'observed other-device mismatch')
    require(isinstance(head.get('lit_aspects'), list), 'original lit aspects missing')
    require(device.get('indication') in ('none', 'WALK', 'DONT_WALK', 'WAIT', 'unknown'),
            'original other-device indication missing')
    location = actor.get_location()
    require(all(math.isfinite(v) for v in (location.x, location.y, location.z)),
            'nonfinite pedestrian position')
    return {
        'frame': frame, 'elapsed_seconds': float(elapsed),
        'actor_id': actor.id, 'actor_type_id': actor.type_id,
        'pedestrian_xy': [float(location.x), float(location.y)],
        'pedestrian_z': float(location.z),
        'official_signal_head_id': head['head_id'],
        'pedestrian_faces_head': head.get('pedestrian_faces_head'),
        'lit_aspects': head['lit_aspects'],
        'other_device_id': device['device_id'],
        'other_device_indication': device['indication'],
        'other_device_mode': device.get('mode', 'unknown'),
        'other_device_countdown': device.get('countdown'),
    }


def capture(world, actor, site, source_root, case_suffix, head_reader,
            device_reader, control_factory, vector_factory, attempt_root,
            ticks=899, camera_readers=None, camera_dimensions=None):
    """Record original observed frames and a sealed receipt; caller owns actor/world.

    A valid capture starts before highway entry and samples the initial state,
    then requests movement for each synchronous tick. A failed sample is never
    published as a complete capture. Braking is requested even on failure.
    """
    verify_site(site, source_root)
    require(case_suffix in ENTER_CASES | WAIT_CASES, 'unknown exact case')
    require(isinstance(ticks, int) and ticks > 0, 'invalid duration')
    require(actor.type_id == site['pedestrian_blueprint_id'], 'actor type mismatch')
    if camera_readers is not None:
        require(set(camera_readers) == set(CAMERAS), 'four named camera sources required')
    dimensions = camera_dimensions or CAMERA_DIMENSIONS
    require(set(dimensions) == set(CAMERAS), 'four named camera dimensions required')
    follower = RouteFollower(case_suffix, site, control_factory, vector_factory)
    output_root = Path(attempt_root)
    output_root.mkdir(parents=True, exist_ok=True)
    require(not (output_root / 'original-frames.json').exists() and
            not (output_root / 'capture-receipt.json').exists(),
            'capture output already exists; use a new attempt directory')
    rows = []
    archives = {}
    media_paths = {}
    try:
        if camera_readers is not None:
            for name in CAMERAS:
                path = output_root / (name + '.png.zip')
                require(not path.exists(), 'camera output already exists; use a new attempt directory')
                archives[name] = ZipFile(path, 'w', compression=ZIP_STORED)
                media_paths[name] = path
        def sample_cameras(row):
            if camera_readers is None:
                return
            row['camera_frames'] = {}
            for name in CAMERAS:
                payload = _image_bytes(camera_readers[name], row['frame'], tuple(dimensions[name]))
                member = f"{row['frame']:08d}.png"
                archives[name].writestr(member, payload)
                row['camera_frames'][name] = {'member': member,
                    'sha256': hashlib.sha256(payload).hexdigest()}
        first = _frame(world, actor, site, head_reader, device_reader)
        require(not inside(first['pedestrian_xy'], site['highway_polygon_xy']),
                'capture starts after highway entry')
        sample_cameras(first)
        rows.append(first)
        previous_frame, previous_time = first['frame'], first['elapsed_seconds']
        for _ in range(ticks):
            follower.apply(actor)
            tick_frame = world.tick()
            row = _frame(world, actor, site, head_reader, device_reader)
            require(row['frame'] == tick_frame == previous_frame + 1,
                    'native frame gap or tick mismatch')
            require(0.035 <= row['elapsed_seconds'] - previous_time <= 0.065,
                    'native capture is not synchronized at 20 Hz')
            require(row['actor_id'] == first['actor_id'] and
                    row['actor_type_id'] == first['actor_type_id'],
                    'pedestrian identity changed')
            require(row['pedestrian_faces_head'] is True,
                    'facing signal observation unavailable')
            sample_cameras(row)
            rows.append(row)
            previous_frame, previous_time = row['frame'], row['elapsed_seconds']
        if case_suffix in WAIT_CASES:
            require(all(not inside(row['pedestrian_xy'], site['highway_polygon_xy']) for row in rows),
                    'wait case entered highway')
        for archive in archives.values():
            archive.close()
        archives.clear()
        path = output_root / 'original-frames.json'
        payload = (json.dumps(rows, indent=2) + '\n').encode()
        temporary = path.with_suffix('.json.tmp')
        temporary.write_bytes(payload)
        temporary.replace(path)
        receipt = {
            'format': 'worker-original-crossing-capture',
            'assignment_id': ASSIGNMENT, 'case_id': ASSIGNMENT + '__' + case_suffix,
            'frame_count': len(rows), 'first_frame': rows[0]['frame'],
            'last_frame': rows[-1]['frame'], 'fps': 20,
            'original_frames': {'path': path.name, 'sha256': hashlib.sha256(payload).hexdigest()},
            'source_refs': site['original_sources'],
            'camera_capture_complete': camera_readers is not None,
            'camera_sources': {name: {'path': path.name,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                'frame_count': len(rows), 'dimensions': list(dimensions[name])}
                for name, path in media_paths.items()},
            'first_highway_entry_frame': next((row['frame'] for row in rows
                if inside(row['pedestrian_xy'], site['highway_polygon_xy'])), None),
            'legal_verdict': None, 'physical_acceptance': False,
        }
        (output_root / 'capture-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        return receipt
    finally:
        for archive in archives.values():
            archive.close()
        if not (output_root / 'capture-receipt.json').exists():
            for path in media_paths.values():
                path.unlink(missing_ok=True)
        actor.apply_control(control_factory(direction=vector_factory(0, 0, 0), speed=0, jump=False))
