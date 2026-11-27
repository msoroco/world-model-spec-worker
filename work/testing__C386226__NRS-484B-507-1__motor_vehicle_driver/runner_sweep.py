"""Source-gated original Native freight-zone capture, with diagnostic preflight."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

from original_runner import load_reviewed_site
from freight_zone import CASES, build_case, measure_history, validate_site

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 900
RATE_HZ = 20
AID = 'testing__C386226__NRS-484B-507-1__motor_vehicle_driver'


class FixtureAdapter:
    def __init__(self):
        self.actors = []

    def spawn_vehicle(self, point, blueprint, role):
        actor = role + str(len(self.actors))
        self.actors.append(actor)
        return actor

    def spawn_materials(self, point, inventory):
        self.actors.append("materials")
        return "materials"

    def spawn_passenger(self, point, blueprint):
        self.actors.append('passenger')
        return 'passenger'

    def set_route(self, *args):
        pass

    def set_conduct(self, *args):
        pass

    def set_passenger_action(self, *args, **kwargs):
        pass

    def set_passenger_dwell(self, *args, **kwargs):
        pass

    def set_material_action(self, *args, **kwargs):
        pass

    def set_freight_arrival(self, *args, **kwargs):
        pass

    def set_freight_headway(self, *args, **kwargs):
        pass

    def destroy(self, actor):
        self.actors.remove(actor)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def exact_case(root, config):
    case_id = config['selected_case_id']
    prefix = AID + '__'
    if not case_id.startswith(prefix):
        raise ValueError('wrong exact selected case')
    case = next((item for item in CASES if item.name == case_id[len(prefix):]), None)
    if case is None or config.get('rate_hz') != RATE_HZ or config.get('duration_s') != 45:
        raise ValueError('exact case or 900-frame capture contract changed')
    cameras = config.get('cameras', [])
    names = [item if isinstance(item, str) else item.get('name') for item in cameras]
    if names != list(CAMERAS):
        raise ValueError('four-camera capture contract changed')
    return case_id, case


def check(root=None):
    root = Path(root or Path(__file__).resolve().parent)
    config = json.loads((root / 'config.json').read_text())
    case_id, case = exact_case(root, config)
    scene = json.loads((root / 'scene.json').read_text())
    if scene.get('case_id') != case_id:
        raise ValueError('scene exact case changed')
    if scene.get('source_kind') == 'synthetic_diagnostic_fixture':
        if scene.get('accepted_original_source') is not False:
            raise ValueError('synthetic provenance required')
        built = build_case(FixtureAdapter(), scene, case)
        if len(built['owned']) != 4:
            raise ValueError('synthetic construction incomplete')
    elif scene.get('source_status') != 'reviewed_original_site_required_at_capture':
        raise ValueError('reviewed original source requirement missing')
    return case_id, case


def capture_original(adapter, manifest_path, site_path, output_dir, root=None, pipeline_factory=None):
    root = Path(root or Path(__file__).resolve().parent)
    case_id, case = check(root)
    site = load_reviewed_site(manifest_path, site_path, case_id)
    validate_site(site, case)
    if not callable(getattr(adapter, 'provenance', None)) or adapter.provenance() != 'original_native':
        raise ValueError('original Native adapter provenance required')
    output = Path(output_dir)
    if not output.is_dir() or not all((output / name).is_file() for name in ('construction.json', 'runner.py', 'config.json')):
        raise ValueError('materialized original Native attempt required')
    if any((output / name).exists() for name in ('history.jsonl', 'camera-frame-map.jsonl', 'capture-seal.json')):
        raise ValueError('refusing to overwrite original capture')
    reviewed_dir = output / 'reviewed-site'
    if reviewed_dir.exists():
        raise ValueError('reviewed source already materialized')
    reviewed_dir.mkdir()
    shutil.copy2(manifest_path, reviewed_dir / 'source-manifest.json')
    shutil.copy2(site_path, reviewed_dir / 'site-context.json')
    built = None
    pipeline = None
    started = False
    finished = False
    try:
        built = build_case(adapter, site, case)
        if not callable(getattr(adapter, 'pipeline_client', None)):
            raise ValueError('original Native PipelineCapture client required')
        if pipeline_factory is None:
            from pipeline_capture import PipelineCapture
            pipeline_factory = PipelineCapture
        config = json.loads((root / 'config.json').read_text())
        pipeline = pipeline_factory(adapter.pipeline_client(), built['ego'], output, case_id,
                                    required_observations=tuple(config.get('required_atoms', [])))
        adapter.start_cameras(output, CAMERAS)
        started = True
        rows, mapping = [], []
        first_frame = first_time = None
        for index in range(FRAMES):
            row = adapter.tick_and_sample()
            if not isinstance(row, dict):
                raise ValueError('original Native observation missing')
            frame = row.get('original_frame')
            elapsed = row.get('elapsed_s')
            if index == 0:
                first_frame, first_time = frame, elapsed
                if type(frame) is not int or type(elapsed) not in (int, float):
                    raise ValueError('original frame/time missing')
            if (row.get('case_id') != case.name or frame != first_frame + index or
                    type(elapsed) not in (int, float) or abs(elapsed - first_time - index / RATE_HZ) > 0.001):
                raise ValueError('same-tick original 20 Hz frame join changed')
            camera_frames = adapter.record_camera_frame(row)
            if camera_frames != {name: frame for name in CAMERAS}:
                raise ValueError('four original camera frames not joined to Native tick')
            captured = pipeline.capture(frame, elapsed)
            if captured.get('frame') != frame or captured.get('time_s') != elapsed:
                raise ValueError('PipelineCapture original frame join differs')
            rows.append(row)
            mapping.append({'original_frame': frame, 'time_s': elapsed,
                            'camera_frames': camera_frames})
        measured = measure_history(rows, case, site)
        videos = adapter.finish_cameras()
        if not isinstance(videos, dict) or set(videos) != set(CAMERAS):
            raise ValueError('four original camera outputs missing')
        for name, path in videos.items():
            target = (output / (name + '.mkv')).resolve()
            if Path(path).resolve() != target or not target.is_file() or not target.stat().st_size:
                raise ValueError('original camera file missing: ' + name)
        pipeline.close(confirmed=True)
        native_sources = adapter.finish_native_capture(output, rows)
        if not isinstance(native_sources, list):
            raise ValueError('original Native source list missing')
        native_sources = ['road.xodr', 'trace.jsonl', 'carla_recorder.log',
                          *[str(path.relative_to(output)) for path in sorted((output / 'capture').rglob('*')) if path.is_file()],
                          *native_sources]
        for item in native_sources:
            path = output / item
            if Path(item).is_absolute() or not path.is_file() or not path.stat().st_size:
                raise ValueError('original Native source missing: ' + str(item))
        def write(name, value):
            (output / name).write_text(value)
        write('history.jsonl', ''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))
        write('camera-frame-map.jsonl', ''.join(json.dumps(row, sort_keys=True) + '\n' for row in mapping))
        write('video_frames.jsonl', ''.join(json.dumps({'video_frame': i, 'carla_frame': row['original_frame'],
            'native_frame': row['original_frame'], 'time_s': row['time_s']}, sort_keys=True) + '\n' for i, row in enumerate(mapping)))
        write('freight-zone-measurement.json', json.dumps(measured, sort_keys=True) + '\n')
        provenance = {'provenance_kind': 'native', 'diagnostic_fixture': False, 'case_id': case_id,
                      'reviewed_manifest_sha256': sha(manifest_path), 'reviewed_site_sha256': sha(site_path)}
        write('acquisition-provenance.json', json.dumps(provenance, sort_keys=True) + '\n')
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
                        for actor in reversed(built['owned']):
                            adapter.destroy(actor)
                finally:
                    restored = adapter.restore_world()
    if restored is not True:
        raise ValueError('original world restoration readback missing')
    names = ['history.jsonl', 'camera-frame-map.jsonl', 'video_frames.jsonl',
             'freight-zone-measurement.json', 'acquisition-provenance.json',
             'reviewed-site/source-manifest.json', 'reviewed-site/site-context.json',
             *[name + '.mkv' for name in CAMERAS], *native_sources]
    seal = {'format': 'freight-zone-original-native-capture-seal', 'case_id': case_id,
            'provenance_kind': 'native', 'diagnostic_fixture': False, 'frames': FRAMES,
            'capture_rate_hz': RATE_HZ, 'reviewed_manifest_sha256': sha(manifest_path),
            'reviewed_site_sha256': sha(site_path),
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'sources': {name: sha(output / name) for name in names}}
    (output / 'capture-seal.json').write_text(json.dumps(seal, indent=2, sort_keys=True) + '\n')
    return {'case_id': case_id, 'frame_count': FRAMES, 'capture_seal_sha256': sha(output / 'capture-seal.json'),
            'physical_visibility_verified': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--reviewed-manifest', default=os.environ.get('C386226_REVIEWED_MANIFEST'))
    parser.add_argument('--reviewed-site', default=os.environ.get('C386226_REVIEWED_SITE'))
    parser.add_argument('--adapter-module', default=os.environ.get('C386226_NATIVE_ADAPTER_MODULE'))
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    case_id, _ = check()
    if args.check:
        print('freight-zone exact case preflight passed: ' + case_id)
        return
    if not all((args.reviewed_manifest, args.reviewed_site, args.adapter_module,
                args.output_dir, args.host, args.port)):
        raise ValueError('reviewed original source and Native adapter arguments required')
    load_reviewed_site(args.reviewed_manifest, args.reviewed_site, case_id)
    source_manifest = json.loads(Path(args.reviewed_manifest).read_text())
    module_path = Path(args.adapter_module)
    if (not module_path.is_file() or module_path.is_symlink() or
            source_manifest.get('native_adapter_sha256') != sha(module_path)):
        raise ValueError('reviewed original Native adapter source hash missing or changed')
    spec = importlib.util.spec_from_file_location('freight_zone_native_adapter', module_path)
    if spec is None or spec.loader is None:
        raise ValueError('original Native adapter module missing')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.open_native_adapter(args.host, args.port)
    try:
        print(capture_original(adapter, args.reviewed_manifest, args.reviewed_site, args.output_dir))
    finally:
        adapter.close()


if __name__ == '__main__':
    main()
