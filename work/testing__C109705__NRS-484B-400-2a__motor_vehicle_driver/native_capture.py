"""Collect a source-bound 45-second Native left-turn attempt.

The injected adapter owns CARLA actors and camera sensors. Each camera callback
must provide the original PNG bytes for the same simulator frame as the ego row.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from approach import measure
from native_map import verify_live_map
from saved_delivery import CAMERAS, FRAMES, PREFIX, SUFFIXES, audit_original_pixels


def _write_jsonl(path: Path, rows: list[dict]) -> str:
    raw = ''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n'
                  for row in rows).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def capture(adapter, case_id: str, map_packet_path: Path, output_root: Path) -> dict:
    """Capture exact frame identities and original camera PNGs from an adapter.

    ``adapter`` exposes world, start(plan), tick(), read_ego(frame),
    read_cameras(frame), brake(), and cleanup(). The capture rejects missing
    callbacks, frame gaps, cadence drift, and malformed original PNG headers.
    Each camera callback supplies its own Native presentation time.
    """
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError('unknown exact approach case')
    binding = verify_live_map(adapter.world, map_packet_path, case_id)
    destination = Path(output_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Native attempt destination already exists')
    root = Path(tempfile.mkdtemp(prefix=destination.name + '.incomplete-',
                                 dir=destination.parent))
    started = False
    opendrive = None
    history: list[dict] = []
    frame_map: list[dict] = []
    archives = {}
    try:
        adapter.start(binding['planned_construction'])
        started = True
        archives = {name: zipfile.ZipFile(root / (name + '.zip'), 'w',
                                         compression=zipfile.ZIP_STORED)
                    for name in sorted(CAMERAS)}
        for index in range(FRAMES):
            tick = adapter.tick()
            frame, time_s = tick['frame'], tick['time_s']
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError('Native frame identity missing')
            if history and (frame != history[-1]['frame'] + 1 or
                            abs(time_s - history[-1]['time_s'] - .05) > .001):
                raise ValueError('Native frame gap or cadence drift')
            ego = adapter.read_ego(frame)
            if ego.get('frame') != frame or ego.get('case_id') != case_id:
                raise ValueError('Native ego frame/case readback differs')
            row = {**ego, 'frame': frame, 'time_s': time_s}
            history.append(row)
            camera_rows = adapter.read_cameras(frame)
            if not isinstance(camera_rows, dict) or set(camera_rows) != CAMERAS:
                raise ValueError('Native four-camera callback set missing')
            camera_times = {}
            for name in sorted(CAMERAS):
                camera = camera_rows[name]
                raw = camera.get('png')
                if (camera.get('frame') != frame or not isinstance(raw, bytes) or
                        len(raw) < 16 or not raw.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ValueError('Native original camera PNG/frame missing: ' + name)
                camera_time = camera.get('time_s')
                if (type(camera_time) not in (int, float) or
                        not math.isfinite(camera_time) or
                        abs(camera_time - time_s) > .001):
                    raise ValueError('Native original camera timestamp drift: ' + name)
                camera_times[name] = camera_time
                archives[name].writestr(f'{index:04d}-{frame}.png', raw)
            frame_map.append({'frame': frame, 'video_frame': index,
                              'carla_frame': frame, 'native_frame': frame,
                              'time_s': time_s,
                              'camera_frames': {name: frame for name in sorted(CAMERAS)},
                              'camera_times_s': camera_times})
        opendrive = adapter.world.get_map().to_opendrive()
        if (not isinstance(opendrive, str) or
                hashlib.sha256(opendrive.encode()).hexdigest() != binding['opendrive_sha256']):
            raise ValueError('Native OpenDRIVE changed during capture')
    except BaseException:
        shutil.rmtree(root)
        raise
    finally:
        try:
            for archive in archives.values():
                archive.close()
            try:
                if started:
                    adapter.brake()
            finally:
                adapter.cleanup()
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
    try:
        context = binding['intersection_context']
        road_bytes = opendrive.encode()
        (root / 'road.xodr').write_bytes(road_bytes)
        context_bytes = (json.dumps(context, sort_keys=True, separators=(',', ':')) + '\n').encode()
        (root / 'intersection-context.json').write_bytes(context_bytes)
        hashes = {'road.xodr': hashlib.sha256(road_bytes).hexdigest(),
                  'intersection-context.json': hashlib.sha256(context_bytes).hexdigest(),
                  'approach-history.jsonl': _write_jsonl(root / 'approach-history.jsonl', history),
                  'video_frames.jsonl': _write_jsonl(root / 'video_frames.jsonl', frame_map)}
        acquisition = {'case_id': case_id,
                       'diagnostic_fixture': not (getattr(adapter, 'native_attested', False)
                                                  and binding['public_highway_reviewed'] is True),
                       'map_binding': binding,
                       'media': {name: {'kind': 'original_native', 'path': name + '.zip',
                                        'sha256': hashlib.sha256((root / (name + '.zip')).read_bytes()).hexdigest()}
                                 for name in sorted(CAMERAS)}}
        acquisition.update({name: {'kind': 'original_native', 'sha256': digest}
                            for name, digest in hashes.items()})
        (root / 'acquisition.json').write_text(json.dumps(acquisition, indent=2) + '\n')
        measured = measure(root)
        pixels = audit_original_pixels(root, case_id,
                                       allow_diagnostic=acquisition['diagnostic_fixture'])
        os.replace(root, destination)
        return {'case_id': case_id, 'frame_count': FRAMES, 'source_sha256': hashes,
                'approach_measurement': measured, 'decoded_frames': pixels['decoded_frames'],
                'physical_completion': False, 'legal_judgment': 'unresolved'}
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
