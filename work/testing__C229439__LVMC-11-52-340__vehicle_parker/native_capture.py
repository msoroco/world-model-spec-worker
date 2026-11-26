"""Acquire original City-space motion and synchronized camera sources.

The adapter is a reviewed local CARLA implementation. This module owns the
case invariants, source joins, actor cleanup, and sealed attempt lifecycle.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from city_space import SOURCE_FIELDS, construct, measure_original
from source_packet import load_reviewed, sha

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 900
HZ = 20


def acquire(adapter, packet_path, case_id, output_dir, *, pipeline_factory=None,
            seal_factory=None, adapter_module_path=None, candidate='primary'):
    packet_path = Path(packet_path).resolve(strict=True)
    packet, scene, case = load_reviewed(packet_path, case_id)
    output = Path(output_dir).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('original attempt output must be fresh')
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    if seal_factory is None:
        from worker_exchange.native_output import seal_capture
        seal_factory = seal_capture
    output.mkdir(parents=True, exist_ok=True)
    retained = output / 'reviewed-sources'
    retained.mkdir()
    shutil.copy2(packet_path, retained / 'city-space-packet.json')
    for entry in packet['sources'].values():
        original = packet_path.parent / entry['path']
        target = retained / entry['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, target)
        if sha(target) != entry['sha256']:
            raise ValueError('retained original source changed')
    if adapter_module_path is not None:
        shutil.copy2(adapter_module_path, retained / 'native-adapter.py')
    built = pipeline = None
    started = finished = False
    rows = []
    camera_rows = []
    try:
        built = construct(adapter, scene, case)
        pipeline = pipeline_factory(adapter.pipeline_client(), built['owned'][1],
                                    output, case_id, required_observations=())
        if candidate == 'primary':
            camera_plan = packet['camera_plan']
        elif candidate == 'fallback1':
            camera_plan = packet.get('fallback_camera_plan')
            if not isinstance(camera_plan, dict) or set(camera_plan) != set(CAMERAS):
                raise ValueError('reviewed fallback camera placements required')
        else:
            raise ValueError('unknown City-space candidate')
        adapter.start_cameras(output, camera_plan)
        started = True
        first_frame = first_time = None
        for index in range(FRAMES):
            adapter.advance_parking(built, index)
            native_frame, elapsed = adapter.tick_world()
            if type(native_frame) is not int or type(elapsed) not in (int, float):
                raise ValueError('original Native frame/time missing')
            if first_frame is None:
                first_frame, first_time = native_frame, elapsed
            if (native_frame != first_frame + index or
                    abs(elapsed - first_time - index / HZ) > .002):
                raise ValueError('original Native cadence or frame gap')
            frames = adapter.camera_frame_ids(native_frame)
            if frames != {name: native_frame for name in CAMERAS}:
                raise ValueError('four original camera frames do not join')
            captured = pipeline.capture(native_frame, elapsed)
            if captured.get('frame') != native_frame or captured.get('time_s') != elapsed:
                raise ValueError('PipelineCapture original frame join differs')
            sample = adapter.sample_parking(built, native_frame)
            if not isinstance(sample, dict):
                raise ValueError('original parking sample missing')
            row = dict(sample, original_frame=native_frame,
                       time_s=index / HZ, vehicle_id=scene['vehicle_id'],
                       parking_person_id=scene['parking_person_id'],
                       official_device_text=scene['official_device_text'],
                       city_vehicle=case.city_vehicle, designated=case.designated,
                       posted=case.posted)
            for field in SOURCE_FIELDS:
                row[field + '_source_sha256'] = scene[field + '_source_sha256']
            rows.append(row)
            camera_rows.append({'frame_index': index, 'native_frame': native_frame,
                                'time_s': index / HZ, 'camera_frames': frames})
        measurement = measure_original(rows, scene, case)
        videos = adapter.finish_cameras()
        finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original videos required')
        for name in CAMERAS:
            target = output / (name + '.mkv')
            if Path(videos[name]).resolve() != target or not target.is_file() or target.stat().st_size == 0:
                raise ValueError('original camera video missing: ' + name)
        pipeline.close(confirmed=True)
        (output / 'original-city-space.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
        (output / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in camera_rows), encoding='utf-8')
        (output / 'city-space-context.json').write_text(json.dumps({
            'format': 'c229439-city-space-context-v1',
            'case_id': case_id, 'scene': scene,
            'reviewed_packet_sha256': sha(packet_path),
            'source_kind': 'original_native'}, sort_keys=True) + '\n', encoding='utf-8')
        from worker_exchange.native_output import FrameMap
        with FrameMap(output / 'video_frames.jsonl') as frame_map:
            for row in camera_rows:
                frame_map.append(row['native_frame'], row['time_s'])
    finally:
        try:
            if pipeline is not None and not pipeline.closed:
                pipeline.close(confirmed=False)
        finally:
            try:
                if started and not finished:
                    adapter.abort_cameras()
            finally:
                try:
                    if built is not None:
                        for actor in reversed(built['owned']):
                            adapter.destroy(actor)
                finally:
                    if adapter.restore_world() is not True:
                        raise ValueError('original Native world restoration readback failed')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_kind': 'original_native', 'physical_acceptance_claimed': False,
        'reviewed_packet_sha256': sha(packet_path)}) + '\n', encoding='utf-8')
    seal_factory(output, frames=FRAMES, restoration={
        'restored': True, 'method': 'owned actors and cameras destroyed; world readback'},
        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'case_id': case_id, 'reviewed_packet_sha256': sha(packet_path),
                 'candidate': candidate,
                 'physical_acceptance_claimed': False})
    return {'case_id': case_id, 'frames': FRAMES,
            'measurement': measurement, 'physical_visibility_verified': False,
            'legal_verdict_claimed': False}
