"""Original 900-tick two-actor Native capture with reviewed source preflight."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

from original_runner import REQUIRED, load_reviewed_site
from through_highway import ASSIGNMENT, CASES, ENGINEERING, construct, control_tick, measure, sample_native_frame

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 900


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / 'config.json').read_text())
    case_id = config['selected_case_id']
    name = case_id.removeprefix(ASSIGNMENT + '__')
    if (not case_id.startswith(ASSIGNMENT + '__') or name not in CASES or
            config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            [c if isinstance(c, str) else c.get('name') for c in config.get('cameras', [])] != list(CAMERAS)):
        raise ValueError('exact 900-frame two-actor capture contract changed')
    scene = json.loads((root / 'scene.json').read_text())
    if scene.get('case_id') != case_id:
        raise ValueError('exact scene identity changed')
    if scene.get('source_kind') == 'synthetic_diagnostic_fixture':
        if scene.get('accepted_original_source') is not False:
            raise ValueError('synthetic provenance changed')
    elif scene.get('source_status') != 'reviewed_original_site_required_at_capture':
        raise ValueError('reviewed source gate missing')
    return case_id, name


def capture_original(adapter, manifest_path, site_path, output_dir, root=None,
                     pipeline_factory=None, adapter_module_path=None):
    root = Path(root or Path(__file__).resolve().parent)
    case_id, name = check(root)
    site = load_reviewed_site(manifest_path, site_path, case_id)
    adapter_module_path = Path(adapter_module_path) if adapter_module_path is not None else None
    source_manifest = json.loads(Path(manifest_path).read_text())
    if (adapter_module_path is None or not adapter_module_path.is_file() or
            adapter_module_path.is_symlink() or
            sha(adapter_module_path) != source_manifest.get('native_adapter_sha256')):
        raise ValueError('reviewed original Native adapter source hash missing or changed')
    if not callable(getattr(adapter, 'provenance', None)) or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    output = Path(output_dir)
    if not output.is_dir() or not all((output / item).is_file() for item in ('construction.json', 'runner.py', 'config.json')):
        raise ValueError('materialized original Native attempt required')
    if any((output / item).exists() for item in ('history.jsonl', 'camera-frame-map.jsonl', 'capture-seal.json')):
        raise ValueError('refusing to overwrite original capture')
    reviewed = output / 'reviewed-site'
    if reviewed.exists():
        raise ValueError('reviewed source already materialized')
    reviewed.mkdir()
    shutil.copy2(manifest_path, reviewed / 'source-manifest.json')
    shutil.copy2(site_path, reviewed / 'site-context.json')
    for source_name in REQUIRED:
        item = source_manifest['sources'][source_name]
        relative = Path(item['path'])
        source = Path(manifest_path).parent / relative
        target = reviewed / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(adapter_module_path, reviewed / 'native-adapter.py')
    world = adapter.world()
    built = pipeline = None
    started = finished = False
    try:
        built = construct(world, site, name, site['map_sha256'])
        if not callable(getattr(adapter, 'pipeline_client', None)):
            raise ValueError('original PipelineCapture client required')
        if pipeline_factory is None:
            from pipeline_capture import PipelineCapture
            pipeline_factory = PipelineCapture
        config = json.loads((root / 'config.json').read_text())
        pipeline = pipeline_factory(adapter.pipeline_client(), built['actors']['through'], output,
                                    case_id, required_observations=tuple(config.get('required_atoms', [])))
        adapter.start_cameras(output, CAMERAS)
        started = True
        rows, mapping = [], []
        first_elapsed = first_native = None
        engineering = ENGINEERING.get(name, {})
        for index in range(FRAMES):
            for role in ('through', 'entering'):
                route = built['routes'][role]['waypoints_xyz']
                target = route[1] if index < 420 else route[-1]
                allow_go = not (role == 'through' and built['request'] == 'yield_request' and 250 <= index < 500)
                if role == 'entering' and index < 200 + round(engineering.get('antecedent_pause_s', 0.0) * 20):
                    allow_go = False
                requested = engineering.get('through_approach_speed_mps', 8.0) if role == 'through' else 8.0
                control_tick(built['actors'][role], target, requested, allow_go=allow_go)
            adapter.tick_world()
            snapshot = world.get_snapshot()
            if index == 0:
                first_elapsed = snapshot.timestamp.elapsed_seconds
                first_native = snapshot.frame
            row = sample_native_frame(world, built['actors'], site, name,
                                      site['map_sha256'], index, first_elapsed)
            if row['native_frame'] != first_native + index:
                raise ValueError('original Native frame gap')
            camera_frames = adapter.camera_frame_ids(row['native_frame'])
            if camera_frames != {camera: row['native_frame'] for camera in CAMERAS}:
                raise ValueError('four camera frames not joined to Native tick')
            captured = pipeline.capture(row['native_frame'], snapshot.timestamp.elapsed_seconds)
            if captured.get('frame') != row['native_frame'] or captured.get('time_s') != snapshot.timestamp.elapsed_seconds:
                raise ValueError('PipelineCapture original frame join differs')
            rows.append(row)
            mapping.append({'frame_index': index, 'native_frame': row['native_frame'],
                            'time_s': row['time_s'], 'camera_frames': camera_frames})
        measured = measure(site, name, site['map_sha256'], rows)
        videos = adapter.finish_cameras()
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original camera outputs missing')
        for camera, path in videos.items():
            target = (output / (camera + '.mkv')).resolve()
            if Path(path).resolve() != target or not target.is_file() or not target.stat().st_size:
                raise ValueError('original camera file missing: ' + camera)
        pipeline.close(confirmed=True)
        native_sources = adapter.finish_native_capture(output, rows)
        if not isinstance(native_sources, list):
            raise ValueError('original Native source list missing')
        native_sources = ['road.xodr', 'trace.jsonl', 'carla_recorder.log',
                          *[str(path.relative_to(output)) for path in sorted((output / 'capture').rglob('*')) if path.is_file()],
                          *native_sources]
        for name in native_sources:
            path = output / name
            if Path(name).is_absolute() or '..' in Path(name).parts or not path.is_file() or not path.stat().st_size:
                raise ValueError('original Native source missing: ' + str(name))
        (output / 'history.jsonl').write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))
        (output / 'camera-frame-map.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping))
        (output / 'video_frames.jsonl').write_text(''.join(json.dumps({'video_frame': i,
            'carla_frame': row['native_frame'], 'native_frame': row['native_frame'],
            'time_s': row['time_s']}, sort_keys=True) + '\n' for i, row in enumerate(mapping)))
        (output / 'two-actor-measurement.json').write_text(json.dumps(measured, sort_keys=True) + '\n')
        provenance = {'provenance_kind': 'native', 'diagnostic_fixture': False, 'case_id': case_id,
                      'reviewed_manifest_sha256': sha(manifest_path), 'reviewed_site_sha256': sha(site_path)}
        (output / 'acquisition-provenance.json').write_text(json.dumps(provenance, sort_keys=True) + '\n')
        finished = True
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
                        for actor in built['actors'].values():
                            actor.destroy()
                finally:
                    restored = adapter.restore_world()
    if restored is not True:
        raise ValueError('original world restoration readback missing')
    names = ['history.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl',
             'two-actor-measurement.json', 'acquisition-provenance.json',
             'reviewed-site/source-manifest.json', 'reviewed-site/site-context.json',
             'reviewed-site/native-adapter.py',
             *['reviewed-site/' + source_manifest['sources'][source_name]['path'] for source_name in REQUIRED],
             *[camera + '.mkv' for camera in CAMERAS], *native_sources]
    seal = {'format': 'through-highway-original-native-capture-seal', 'case_id': case_id,
            'provenance_kind': 'native', 'diagnostic_fixture': False, 'frames': FRAMES,
            'capture_rate_hz': 20, 'reviewed_manifest_sha256': sha(manifest_path),
            'reviewed_site_sha256': sha(site_path),
            'restoration': {'restored': True}, 'encoder_exit_codes': {},
            'native_revision': {'construction_sha256': sha(output / 'construction.json'),
                                'runner_sha256': sha(output / 'runner.py')},
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': {name: sha(output / name) for name in names}}
    (output / 'capture-seal.json').write_text(json.dumps(seal, indent=2, sort_keys=True) + '\n')
    return {'case_id': case_id, 'frame_count': FRAMES,
            'capture_seal_sha256': sha(output / 'capture-seal.json'),
            'physical_visibility_verified': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-manifest', default=os.environ.get('C179789_REVIEWED_MANIFEST'))
    parser.add_argument('--reviewed-site', default=os.environ.get('C179789_REVIEWED_SITE'))
    parser.add_argument('--adapter-module', default=os.environ.get('C179789_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    case_id, _ = check()
    if args.check:
        print('through-highway exact case preflight passed: ' + case_id)
        return
    if not all((args.reviewed_manifest, args.reviewed_site, args.adapter_module,
                args.output_dir, args.host, args.port)):
        raise ValueError('reviewed original source and Native adapter arguments required')
    load_reviewed_site(args.reviewed_manifest, args.reviewed_site, case_id)
    source = json.loads(Path(args.reviewed_manifest).read_text())
    module_path = Path(args.adapter_module)
    if not module_path.is_file() or module_path.is_symlink() or source.get('native_adapter_sha256') != sha(module_path):
        raise ValueError('reviewed original Native adapter source hash missing or changed')
    spec = importlib.util.spec_from_file_location('through_highway_native_adapter', module_path)
    if spec is None or spec.loader is None:
        raise ValueError('original Native adapter module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        print(capture_original(adapter, args.reviewed_manifest, args.reviewed_site,
                               args.output_dir, adapter_module_path=module_path))
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
