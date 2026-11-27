"""Original Native acquisition protocol for the four stop-intersection cases.

The adapter supplies actual simulator ticks, actor states, camera PNG bytes and
trace/video mappings. The worker does not synthesize any of those observations.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from stop_site import create, validate_site


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
        if not (output / 'construction.json').is_file() or \
                (output / 'original-attempt').exists() or \
                (output / 'capture-seal.json').exists():
            raise ValueError('refusing to overwrite prior original attempt')
    else:
        output.mkdir(parents=True)
    original = output / 'original-attempt'
    original.mkdir()
    _write_json(output / 'config.json', config)
    reviewed = Path(site_path).resolve()
    sealed_site = json.loads(json.dumps(site))
    (original / 'source-review').mkdir()
    for name, source in sealed_site['sources'].items():
        source_path = Path(source['path'])
        if not source_path.is_absolute():
            source_path = reviewed.parent / source_path
        destination = original / 'source-review' / (name + source_path.suffix)
        shutil.copy2(source_path, destination)
        if _sha(destination.read_bytes()) != source['sha256']:
            raise ValueError('reviewed source changed during original acquisition: ' + name)
        source['path'] = 'source-review/' + destination.name
    _write_json(original / 'site-packet.json', sealed_site)
    actors = None
    archives = {}
    rows = []
    mappings = []
    traces = []
    video_frames = []
    restored = False
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
        media = adapter.finalize_media(output, tuple(VIEWS), tuple(mappings))
        if not isinstance(media, dict) or set(media) != set(VIEWS) | {'raw'} or \
                any(Path(media[name]).resolve() != (output / (name + '.mkv')).resolve() or
                    not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                    for name in media):
            raise ValueError('original encoded media incomplete')
    finally:
        for archive in archives.values():
            archive.close()
        if actors is not None:
            actors.close()
        restored = adapter.close() is True
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
    if not restored:
        raise ValueError('Native world restoration not verified')
    source_names = ['original-attempt/history.jsonl', 'original-attempt/frame-map.json',
                    'original-attempt/site-packet.json', 'original-attempt/inventory.json',
                    'trace.jsonl', 'video_frames.jsonl']
    source_names += ['original-attempt/' + name + '.zip' for name in VIEWS]
    source_names += ['original-attempt/' + source['path'] for source in sealed_site['sources'].values()]
    source_names += [name + '.mkv' for name in (*VIEWS, 'raw')]
    _write_json(output / 'capture-seal.json', {
        'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
        'sources': {name: _sha((output / name).read_bytes()) for name in source_names},
        'native_revision': {'construction_sha256': _sha((output / 'construction.json').read_bytes()),
                            'runner_sha256': _sha((output / 'runner.py').read_bytes())}})
    return {'case_id': case, 'frame_count': len(rows), 'output': str(output),
            'physical_acceptance_claimed': False}
