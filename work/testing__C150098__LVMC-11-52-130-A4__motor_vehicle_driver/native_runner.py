"""Source-gated original hydrant capture through a local Native adapter.

Only a locally reviewed packet and an adapter connected to CARLA can execute
this path. CPU fakes exercise the acquisition protocol, not physical success.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from hydrant import ASSIGNMENT, build_case, measure_original_history
from native_packet import VIEWS, validate_packet

FRAMES = 900
HZ = 20
CAMERAS = tuple(name for name, _, _ in VIEWS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def capture_original(adapter, packet_path, case_id, output_dir, *, pipeline_factory=None,
                     adapter_module_path=None):
    """Capture original sources without overwriting an existing attempt."""
    packet_path, output = Path(packet_path).resolve(), Path(output_dir)
    site, case, hashes, cameras = validate_packet(packet_path, case_id)
    if output.exists():
        raise ValueError('original Native attempt already exists')
    if not callable(getattr(adapter, 'provenance', None)) or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter required')
    if not callable(getattr(adapter, 'verify_loaded_map', None)) or not adapter.verify_loaded_map(hashes['opendrive']):
        raise ValueError('loaded Native map differs from reviewed map')
    if pipeline_factory is None:
        from pipeline_capture import PipelineCapture
        pipeline_factory = PipelineCapture
    output.mkdir(parents=True)
    source_dir = output / 'reviewed-packet'
    source_dir.mkdir()
    shutil.copy2(packet_path, source_dir / 'reviewed-site.json')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if adapter_module_path is not None:
        adapter_module_path = Path(adapter_module_path)
        binding = packet.get('native_adapter')
        if (not isinstance(binding, dict) or binding.get('sha256') != sha(adapter_module_path)
                or not binding.get('citation') or not binding.get('reviewer')):
            raise ValueError('hash-bound reviewed Native adapter required')
        shutil.copy2(adapter_module_path, source_dir / 'native-adapter.py')
    for item in packet['sources'].values():
        relative = Path(item['path'])
        target = source_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(packet_path.parent / relative, target)
        if sha(target) != item['sha256']:
            raise ValueError('reviewed source changed during Native retention')
    site_path = output / 'site.json'
    site_path.write_text(json.dumps(site, sort_keys=True) + '\n', encoding='utf-8')
    site_sha = sha(site_path)
    built = pipeline = None
    cameras_started = cameras_finished = False
    rows, joins = [], []
    try:
        actor_length = adapter.vehicle_body_length_m()
        built = build_case(adapter, site, case, actor_length)
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
            sample = adapter.sample_body_hydrant(built, frame)
            if not isinstance(sample, dict):
                raise ValueError('original body and hydrant sample missing')
            row = dict(sample, case_id=case_id, frame=frame, time_s=index / HZ,
                       site_sha256=site_sha, map_sha256=site['map_sha256'],
                       hydrant_identity_sha256=site['hydrant_identity_sha256'],
                       hydrant_geometry_sha256=site['hydrant_geometry_sha256'],
                       parallel_parking_authority_sha256=site['parallel_parking_authority_sha256'],
                       camera_plan_sha256=site['camera_plan_sha256'])
            if row.get('exception_kind') != case.exception:
                raise ValueError('original exception source differs')
            rows.append(row)
            joins.append(dict(frame_index=index, native_frame=frame,
                              time_s=index / HZ, camera_frames=camera_frames))
        videos = adapter.finish_cameras()
        cameras_finished = True
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original camera videos required')
        for name in CAMERAS:
            expected = output / (name + '.mkv')
            if Path(videos[name]).resolve() != expected.resolve() or not expected.is_file() or not expected.stat().st_size:
                raise ValueError('original camera video missing: ' + name)
        pipeline.close(confirmed=True)
        frame_map = output / 'camera-frame-map.jsonl'
        frame_map.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in joins),
                             encoding='utf-8')
        video_map = output / 'video_frames.jsonl'
        video_map.write_text(''.join(json.dumps({'video_frame': i,
            'carla_frame': row['native_frame'], 'native_frame': row['native_frame'],
            'time_s': row['time_s']}, sort_keys=True) + '\n'
            for i, row in enumerate(joins)), encoding='utf-8')
        map_sha = sha(frame_map)
        for row in rows:
            row['frame_map_sha256'] = map_sha
        measure_original_history(rows, site, case)
        history = output / 'original-hydrant-history.jsonl'
        history.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
                           encoding='utf-8')
        manifest = {'site.json': {'kind': 'original_native', 'sha256': site_sha},
                    'original-hydrant-history.jsonl': {'kind': 'original_native',
                                                       'sha256': sha(history)}}
        (output / 'source-manifest.json').write_text(json.dumps(manifest, sort_keys=True) + '\n',
                                                      encoding='utf-8')
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
    files = ('site.json', 'original-hydrant-history.jsonl', 'camera-frame-map.jsonl',
             'video_frames.jsonl', *(name + '.mkv' for name in CAMERAS),
             'reviewed-packet/reviewed-site.json',
             *(str(Path('reviewed-packet') / item['path']) for item in packet['sources'].values()))
    if adapter_module_path is not None:
        files += ('reviewed-packet/native-adapter.py',)
    seal = {'format': 'hydrant-original-native-seal-v1', 'case_id': case_id,
            'provenance_kind': 'native', 'diagnostic_fixture': False,
            'frames': FRAMES, 'capture_rate_hz': HZ,
            'reviewed_packet_sha256': sha(packet_path),
            'restoration': {'restored': True},
            'sources': {name: sha(output / name) for name in files}}
    seal_path = output / 'capture-seal.json'
    seal_path.write_text(json.dumps(seal, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {'case_id': case_id, 'frames': FRAMES,
            'capture_seal_sha256': sha(seal_path),
            'original_history_sha256': sha(output / 'original-hydrant-history.jsonl'),
            'physical_visibility_verified': False, 'legal_verdict_claimed': False}
