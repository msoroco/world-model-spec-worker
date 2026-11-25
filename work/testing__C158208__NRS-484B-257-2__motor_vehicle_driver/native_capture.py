"""Original Native acquisition protocol for the four yield-intersection cases.

The adapter supplies actual simulator ticks, actor states, camera PNG bytes and
trace/video mappings. The worker does not synthesize any of those observations.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

from yield_site import create, validate_site


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def capture(adapter, config, site_path, output):
    """Acquire one exact 900-frame attempt and retain its original sources."""
    case = config['selected_case_id']
    site = validate_site(site_path, case)
    output = Path(output)
    if output.exists():
        raise ValueError('refusing to overwrite prior original attempt')
    output.mkdir(parents=True)
    original = output / 'original-attempt'
    original.mkdir()
    _write_json(output / 'config.json', config)
    _write_json(original / 'site-packet.json', site)
    actors = None
    archives = {}
    rows = []
    mappings = []
    traces = []
    video_frames = []
    try:
        actors = create(adapter.world, site_path, adapter.transform_factory, case)
        cameras = adapter.attach_cameras(actors, config['cameras'])
        if set(cameras) != set(VIEWS):
            raise ValueError('four original camera sources were not attached')
        for name in VIEWS:
            archives[name] = zipfile.ZipFile(original / (name + '.zip'), 'x',
                                              compression=zipfile.ZIP_STORED)
        first_frame = None
        first_time = None
        for index in range(config['frame_count']):
            adapter.request_case_control(actors, site, config['case']['draft_variables'],
                                         config['control'], index)
            sample = adapter.tick_and_read(actors, cameras)
            if not isinstance(sample, dict):
                raise ValueError('Native tick returned no source sample')
            frame = sample.get('frame')
            time_s = sample.get('time_s')
            if type(frame) is not int or type(time_s) not in (int, float):
                raise ValueError('original frame/time missing')
            first_frame = frame if first_frame is None else first_frame
            first_time = time_s if first_time is None else first_time
            if frame != first_frame + index or abs(time_s - first_time - index / 20) > .005:
                raise ValueError('original Native frame/time gap')
            raw_frames = sample.get('camera_png', {})
            if set(raw_frames) != set(VIEWS):
                raise ValueError('original camera frame missing')
            hashes = {}
            for name in VIEWS:
                raw = raw_frames[name]
                if not isinstance(raw, bytes) or not raw.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('invalid original camera PNG')
                filename = f'{index:04d}-{frame}.png'
                archives[name].writestr(filename, raw)
                hashes[name] = {'source_sha256': _sha(raw), 'archive_member': filename}
            state = sample.get('state')
            if not isinstance(state, dict):
                raise ValueError('original actor/device state missing')
            trace = sample.get('trace')
            image = sample.get('video_frame')
            if not isinstance(trace, dict) or trace.get('frame') != frame or \
                    trace.get('time_s') != time_s or not isinstance(image, dict) or \
                    image.get('video_frame') != index or \
                    image.get('carla_frame') != frame or image.get('time_s') != time_s:
                raise ValueError('original Native trace/video join missing')
            rows.append({'case_id': case, 'source_packet_sha256': _sha((original / 'site-packet.json').read_bytes()),
                         'original_frame': frame, 'time_s': time_s,
                         'native_state': state, 'camera_frames': hashes})
            mappings.append({'video_frame': index, 'frame': frame, 'time_s': time_s})
            traces.append(trace)
            video_frames.append(image)
    finally:
        for archive in archives.values():
            archive.close()
        if actors is not None:
            actors.close()
        adapter.close()
    if len(rows) != config['frame_count']:
        raise ValueError('original attempt incomplete')
    history = original / 'history.jsonl'
    history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    frame_map = original / 'frame-map.json'
    _write_json(frame_map, {'case_id': case, 'frames': mappings})
    (output / 'trace.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                               for row in traces))
    (output / 'video_frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                                      for row in video_frames))
    _write_json(original / 'inventory.json', {
        'case_id': case, 'diagnostic_fixture': False, 'frame_count': len(rows),
        'history_sha256': _sha(history.read_bytes()),
        'frame_map_sha256': _sha(frame_map.read_bytes()),
        'site_sha256': _sha((original / 'site-packet.json').read_bytes()),
        'camera_media_sha256': {name: _sha((original / (name + '.zip')).read_bytes())
                                for name in VIEWS},
        'physical_acceptance_claimed': False})
    return {'case_id': case, 'frame_count': len(rows), 'output': str(output),
            'physical_acceptance_claimed': False}
