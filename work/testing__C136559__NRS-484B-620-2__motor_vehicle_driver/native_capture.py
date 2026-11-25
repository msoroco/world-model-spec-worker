"""Acquire and source-seal one original 900-frame signed-zone attempt.

The local Native adapter supplies all simulator states, controls and PNG bytes.
No diagnostic fixture is accepted through this path.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from saved_audit import audit as audit_saved
from speed_site import validate_packet
from speed_zone import build_case


VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def capture(adapter, config, site_path, output):
    packet, site, case = validate_packet(site_path, config['selected_case_id'])
    output = Path(output)
    if output.exists():
        if not (output / 'construction.json').is_file() or \
                (output / 'original-attempt').exists() or \
                (output / 'capture-seal.json').exists():
            raise ValueError('refusing to overwrite original attempt')
    else:
        output.mkdir(parents=True)
    original = output / 'original-attempt'
    original.mkdir()
    (original / 'source-review').mkdir()
    sealed_packet = json.loads(json.dumps(packet))
    for name, source in sealed_packet['sources'].items():
        path = Path(source['path'])
        if not path.is_absolute():
            path = Path(site_path).resolve().parent / path
        dest = original / 'source-review' / (name + path.suffix)
        shutil.copy2(path, dest)
        if sha(dest) != source['sha256']:
            raise ValueError('reviewed speed source changed during acquisition')
        source['path'] = 'source-review/' + dest.name
    write(original / 'site-packet.json', sealed_packet)
    owned = ()
    archives = {}
    rows = []
    mappings = []
    traces = []
    video_frames = []
    restored = False
    try:
        built = build_case(adapter, site, case)
        owned = built['owned']
        cameras = adapter.attach_cameras(built['ego'], config['cameras'])
        if set(cameras) != set(VIEWS):
            raise ValueError('four original cameras absent')
        for name in VIEWS:
            archives[name] = zipfile.ZipFile(original / (name + '.zip'), 'x',
                                              compression=zipfile.ZIP_STORED)
        for index in range(config['frame_count']):
            adapter.request_speed(built['ego'], case.requested_mph, case.zone_mode, index)
            sample = adapter.tick_and_read(built, cameras)
            if not isinstance(sample, dict) or sample.get('original_frame') != index or \
                    not isinstance(sample.get('original_time_s'), (int, float)) or \
                    abs(sample['original_time_s'] - index / 20) > .005:
                raise ValueError('original frame/time gap')
            camera_png = sample.get('camera_png', {})
            if set(camera_png) != set(VIEWS):
                raise ValueError('original camera frame absent')
            hashes = {}
            for name in VIEWS:
                image = camera_png[name]
                if not isinstance(image, bytes) or not image.startswith(b'\x89PNG\r\n\x1a\n'):
                    raise ValueError('invalid original camera PNG')
                member = f'{index:04d}.png'
                archives[name].writestr(member, image)
                hashes[name] = {'member': member, 'sha256': hashlib.sha256(image).hexdigest()}
            state = sample.get('state')
            trace = sample.get('trace')
            video = sample.get('video_frame')
            if not isinstance(state, dict) or not isinstance(trace, dict) or \
                    trace.get('original_frame') != index or not isinstance(video, dict) or \
                    video.get('video_frame') != index or video.get('original_frame') != index:
                raise ValueError('original Native state/trace/video join absent')
            row = dict(state, original_frame=index, original_time_s=sample['original_time_s'],
                       source_sha256=sha(original / 'site-packet.json'),
                       zone_establishment_source_sha256=site['zone_establishment_source_sha256'],
                       zone_extent_source_sha256=site['zone_extent_source_sha256'],
                       sign_readback_source_sha256=built['sign_readback']['source_sha256'],
                       map_source_sha256=site['road_source_sha256'],
                       direction=case.direction, sign_direction=case.direction,
                       vehicle_class=site['vehicle_class'])
            rows.append(row)
            mappings.append({'video_frame': index, 'original_frame': index,
                             'time_s': sample['original_time_s'], 'camera_frames': hashes})
            traces.append(trace)
            video_frames.append(video)
        media = adapter.finalize_media(output, VIEWS, tuple(mappings))
        if not isinstance(media, dict) or set(media) != set(VIEWS) | {'raw'} or any(
                Path(media[name]).resolve() != (output / (name + '.mkv')).resolve() or
                not Path(media[name]).is_file() or Path(media[name]).stat().st_size == 0
                for name in media):
            raise ValueError('original encoded media incomplete')
    finally:
        for archive in archives.values():
            archive.close()
        for actor in reversed(owned):
            adapter.destroy(actor)
        restored = adapter.close() is True
    if not restored or len(rows) != 900:
        raise ValueError('Native restoration or capture incomplete')
    capture_path = original / 'capture.json'
    write(capture_path, {'case_id': config['selected_case_id'], 'cell_id': 'C136559',
                         'law_id': 'NRS-484B-620-2', 'authorized_speed_mph': 25.0,
                         'map_source_sha256': site['road_source_sha256'],
                         'zone_establishment_source_sha256': site['zone_establishment_source_sha256'],
                         'zone_extent_source_sha256': site['zone_extent_source_sha256'],
                         'sign_instruction_source_sha256': site['sign_instruction_source_sha256'],
                         'camera_plan_sha256': hashlib.sha256(json.dumps(config['cameras'],
                                                                          sort_keys=True).encode()).hexdigest(),
                         'ego_blueprint': adapter.ego_blueprint_id(built['ego']),
                         'original_rows': rows, 'diagnostic_fixture': False})
    seal_path = original / 'capture-source-seal.json'
    write(seal_path, {'case_id': config['selected_case_id'], 'capture_sha256': sha(capture_path)})
    audit_saved(capture_path, seal_path, config['selected_case_id'])
    write(original / 'frame-map.json', {'case_id': config['selected_case_id'], 'frames': mappings})
    (output / 'trace.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in traces))
    (output / 'video_frames.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in video_frames))
    names = ['original-attempt/capture.json', 'original-attempt/capture-source-seal.json',
             'original-attempt/site-packet.json', 'original-attempt/frame-map.json',
             'trace.jsonl', 'video_frames.jsonl']
    names += ['original-attempt/' + source['path'] for source in sealed_packet['sources'].values()]
    names += ['original-attempt/' + name + '.zip' for name in VIEWS]
    names += [name + '.mkv' for name in (*VIEWS, 'raw')]
    write(output / 'capture-seal.json', {
        'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
        'sources': {name: sha(output / name) for name in names},
        'native_revision': {'construction_sha256': sha(output / 'construction.json'),
                            'runner_sha256': sha(output / 'runner.py')}})
    return {'case_id': config['selected_case_id'], 'frame_count': len(rows),
            'physical_acceptance_claimed': False}
