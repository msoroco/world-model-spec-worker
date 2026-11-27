"""Acquire an original red-curb stop interval and its four Native cameras.

Local reviewers provide a source-hashed adapter. This module requires original
frame joins, a complete halt interval, decoder inputs and world restoration.
It never interprets legal compliance or treats a synthetic fixture as pixels.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from red_curb import construct, measure_activity
from source_packet import CAMERAS, load_reviewed, sha

HZ = 20
DEFAULT_FRAMES = 36120  # 1,806 seconds; covers the 1,801-second boundary.


def acquire(adapter, packet_path, case_id, output_dir, *, pipeline_factory=None,
            seal_factory=None, frame_map_factory=None, adapter_module_path=None, candidate='primary',
            frame_count=DEFAULT_FRAMES):
    packet_path = Path(packet_path).resolve(strict=True)
    packet, scene, case = load_reviewed(packet_path, case_id)
    if candidate not in ('primary', 'fallback1'):
        raise ValueError('unknown red-curb candidate')
    if type(frame_count) is not int or frame_count < (case.duration_s * HZ + 1):
        raise ValueError('capture must cover full original halt interval')
    output = Path(output_dir).resolve()
    if output.exists() and any((output / name).exists() for name in (
            'reviewed-sources', 'capture-seal.json', 'native-exit.json',
            'original-red-curb-events.jsonl', 'trace.jsonl', 'overview.mkv')):
        raise ValueError('original attempt output must be fresh')
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    if seal_factory is None:
        from worker_exchange.native_output import seal_capture
        seal_factory = seal_capture
    if frame_map_factory is None:
        from worker_exchange.native_output import FrameMap
        frame_map_factory = FrameMap
    output.mkdir(parents=True, exist_ok=True)
    retained = output / 'reviewed-sources'
    retained.mkdir()
    shutil.copy2(packet_path, retained / 'red-curb-packet.json')
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
    events = []
    camera_rows = []
    try:
        built = construct(adapter, scene, case)
        vehicle = built['owned'][0]
        pipeline = pipeline_factory(adapter.pipeline_client(), vehicle, output,
                                    case_id, required_observations=())
        camera_plan = packet['camera_plan'] if candidate == 'primary' else packet.get('fallback_camera_plan')
        if not isinstance(camera_plan, dict) or set(camera_plan) != set(CAMERAS):
            raise ValueError('reviewed candidate camera placements required')
        readback = adapter.start_cameras(output, camera_plan)
        if not isinstance(readback, dict) or set(readback) != set(CAMERAS) or not all(readback.values()):
            raise ValueError('four-camera Native readback missing')
        started = True
        first_frame = first_time = None
        for index in range(frame_count):
            adapter.advance_halt(built, index, HZ)
            native_frame, elapsed = adapter.tick_world()
            if type(native_frame) is not int or type(elapsed) not in (int, float):
                raise ValueError('original Native frame/time missing')
            if first_frame is None:
                first_frame, first_time = native_frame, elapsed
            if native_frame != first_frame + index or abs(elapsed - first_time - index / HZ) > .002:
                raise ValueError('original Native cadence or frame gap')
            frames = adapter.camera_frame_ids(native_frame)
            if frames != {name: native_frame for name in CAMERAS}:
                raise ValueError('four original camera frames do not join')
            captured = pipeline.capture(native_frame, elapsed)
            if captured.get('frame') != native_frame or captured.get('time_s') != elapsed:
                raise ValueError('PipelineCapture original frame join differs')
            event = adapter.sample_halt_event(built, native_frame)
            if event is not None:
                if not isinstance(event, dict):
                    raise ValueError('original halt event sample malformed')
                if event.get('original_frame') != native_frame:
                    raise ValueError('original halt event frame join differs')
                events.append(event)
            camera_rows.append({'frame_index': index, 'native_frame': native_frame,
                                'time_s': index / HZ, 'camera_frames': frames})
        measurement = measure_activity(events, scene, case)
        videos = adapter.finish_cameras()
        finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original videos required')
        for name in CAMERAS:
            target = output / (name + '.mkv')
            if Path(videos[name]).resolve() != target or not target.is_file() or target.stat().st_size == 0:
                raise ValueError('original camera video missing: ' + name)
        pipeline.close(confirmed=True)
        (output / 'original-red-curb-events.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in events), encoding='utf-8')
        (output / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in camera_rows), encoding='utf-8')
        (output / 'red-curb-context.json').write_text(json.dumps({
            'format': 'c229452-red-curb-context-v1', 'case_id': case_id,
            'scene': scene, 'reviewed_packet_sha256': sha(packet_path),
            'source_kind': 'original_native'}, sort_keys=True) + '\n', encoding='utf-8')
        with frame_map_factory(output / 'video_frames.jsonl') as frame_map:
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
    seal_factory(output, frames=frame_count, restoration={
        'restored': True, 'method': 'owned actors and cameras destroyed; world readback'},
        errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
        context={'case_id': case_id, 'reviewed_packet_sha256': sha(packet_path),
                 'candidate': candidate, 'physical_acceptance_claimed': False})
    return {'case_id': case_id, 'frames': frame_count,
            'measurement': measurement, 'physical_visibility_verified': False,
            'legal_verdict_claimed': False}
