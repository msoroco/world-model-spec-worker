"""Original flashing-red acquisition through a locally reviewed CARLA adapter."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from flashing_red_native import build_case, measure_original
from native_packet import VIEWS, validate_packet

HZ = 20
FRAMES = 900
CAMERAS = tuple(name for name, _, _ in VIEWS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture_original(adapter, packet_path, case_id, output_dir, *, pipeline_factory=None,
                     seal_factory=None, adapter_module_path=None):
    packet_path, output = Path(packet_path).resolve(), Path(output_dir)
    site, case, _, cameras = validate_packet(packet_path, case_id)
    if output.exists() and any((output / name).exists() for name in
                               ('capture-seal.json', 'original-flashing-red-history.jsonl',
                                'reviewed-packet')):
        raise ValueError('original Native attempt already exists')
    if not callable(getattr(adapter, 'provenance', None)) or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter required')
    if not callable(getattr(adapter, 'verify_loaded_map', None)) or not adapter.verify_loaded_map(site['map_sha256']):
        raise ValueError('loaded Native map differs from reviewed map')
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    output.mkdir(parents=True, exist_ok=True)
    source_dir = output / 'reviewed-packet'
    source_dir.mkdir()
    shutil.copy2(packet_path, source_dir / 'reviewed-site.json')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if adapter_module_path is not None:
        module_path = Path(adapter_module_path)
        binding = packet.get('native_adapter')
        if (not isinstance(binding, dict) or binding.get('sha256') != sha(module_path)
                or not binding.get('citation') or not binding.get('reviewer')):
            raise ValueError('hash-bound reviewed Native adapter required')
        shutil.copy2(module_path, source_dir / 'native-adapter.py')
    for item in packet['sources'].values():
        relative = Path(item['path'])
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packet_path.parent / relative, target)
        if sha(target) != item['sha256']:
            raise ValueError('reviewed source changed during Native retention')
    site_path = output / 'site.json'
    site_path.write_text(json.dumps(site, sort_keys=True) + '\n', encoding='utf-8')
    site_hash = sha(site_path)
    built = pipeline = None
    cameras_started = cameras_finished = False
    rows, joins = [], []
    try:
        config = json.loads((output / 'config.json').read_text(encoding='utf-8'))
        built = build_case(adapter, site, case, config.get('engineering'))
        pipeline = pipeline_factory(adapter.pipeline_client(), built['ego'], output,
                                    case_id, required_observations=())
        adapter.start_cameras(output, cameras)
        cameras_started = True
        first_frame = first_time = None
        for index in range(FRAMES):
            adapter.advance_case(built, case, index, FRAMES)
            frame, elapsed = adapter.tick_world()
            if type(frame) is not int or type(elapsed) not in (int, float):
                raise ValueError('original Native frame or time missing')
            if first_frame is None:
                first_frame, first_time = frame, elapsed
            if frame != first_frame + index or abs(elapsed - first_time - index / HZ) > .002:
                raise ValueError('original Native frame gap or cadence drift')
            camera_frames = adapter.camera_frame_ids(frame)
            if camera_frames != {name: frame for name in CAMERAS}:
                raise ValueError('four cameras not joined to original Native frame')
            captured = pipeline.capture(frame, elapsed)
            if captured.get('frame') != frame or captured.get('time_s') != elapsed:
                raise ValueError('PipelineCapture frame join mismatch')
            sample = adapter.sample_signal_vehicle_occluder(built, frame)
            if not isinstance(sample, dict):
                raise ValueError('original physical signal, vehicle or occluder sample missing')
            row = dict(sample, case_id=case_id, frame=frame, time_s=index / HZ,
                       site_sha256=site_hash, map_sha256=site['map_sha256'],
                       signal_identity_sha256=site['signal_identity_sha256'],
                       occluder_identity_sha256=site['occluder_identity_sha256'],
                       stop_geometry_sha256=site['stop_geometry_sha256'],
                       camera_plan_sha256=site['camera_plan_sha256'])
            rows.append(row)
            joins.append({'frame_index': index, 'native_frame': frame,
                          'time_s': index / HZ, 'camera_frames': camera_frames})
        videos = adapter.finish_cameras()
        cameras_finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original camera videos required')
        for name in CAMERAS:
            video = output / (name + '.mkv')
            if Path(videos[name]).resolve() != video.resolve() or not video.is_file() or not video.stat().st_size:
                raise ValueError('original camera video missing: ' + name)
        pipeline.close(confirmed=True)
        frame_map = output / 'camera-frame-map.jsonl'
        frame_map.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in joins),
                             encoding='utf-8')
        (output / 'video_frames.jsonl').write_text(''.join(json.dumps({
            'video_frame': i, 'carla_frame': row['native_frame'],
            'native_frame': row['native_frame'], 'time_s': row['time_s']},
            sort_keys=True) + '\n' for i, row in enumerate(joins)), encoding='utf-8')
        for row in rows:
            row['frame_map_sha256'] = sha(frame_map)
        measure_original(rows, site, case)
        history = output / 'original-flashing-red-history.jsonl'
        history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
                           encoding='utf-8')
        (output / 'source-manifest.json').write_text(json.dumps({
            'site.json': {'kind': 'original_native', 'sha256': site_hash},
            history.name: {'kind': 'original_native', 'sha256': sha(history)}},
            sort_keys=True) + '\n', encoding='utf-8')
    finally:
        try:
            if pipeline is not None and not pipeline.closed:
                pipeline.close(confirmed=False)
        finally:
            try:
                if cameras_started and not cameras_finished:
                    adapter.abort_cameras()
            finally:
                try:
                    if built is not None:
                        for actor in reversed(built['owned']):
                            adapter.destroy(actor)
                finally:
                    if adapter.restore_world() is not True:
                        raise ValueError('original Native world restoration readback missing')
    (output / 'acquisition-provenance.json').write_text(json.dumps({
        'provenance_kind': 'native', 'diagnostic_fixture': False,
        'source_kind': 'original_native', 'physical_acceptance_claimed': False}) + '\n',
        encoding='utf-8')
    if seal_factory is None:
        from worker_exchange.native_output import seal_capture
        seal_factory = seal_capture
    seal_factory(output, frames=FRAMES,
                 restoration={'restored': True,
                              'method': 'owned actors and sensors; Native world settings readback'},
                 errors=[], encoder_exit_codes={name: 0 for name in CAMERAS},
                 context={'case_id': case_id, 'reviewed_packet_sha256': sha(packet_path),
                          'post_stop_rules': 'unresolved_applicable_rules'})
    seal_path = output / 'capture-seal.json'
    if not seal_path.is_file():
        raise ValueError('canonical original capture seal missing')
    return {'case_id': case_id, 'frames': FRAMES, 'capture_seal_sha256': sha(seal_path),
            'original_history_sha256': sha(output / 'original-flashing-red-history.jsonl'),
            'physical_visibility_verified': False, 'legal_verdict_claimed': False}
