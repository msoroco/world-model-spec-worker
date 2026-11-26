"""Acquire synchronized original camera sources during the Native case ticks.

The adapter owns pixel encoding. This layer requires frame joins and original
source files, then leaves full decode and pixel review to independent audits.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import shutil

from independent_delivery_audit import CAMERAS
from native_history_capture import capture_original_history
from parking import CASES, build_case
from reviewed_site import verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def capture(adapter, packet_path: Path, source_root: Path, case_id: str,
            body_length_m: float, attempt: Path,
            camera_lateral_offset_m: float = 0.0) -> dict:
    packet = verify(packet_path, source_root)
    prefix = packet['assignment_id'] + '__'
    if not case_id.startswith(prefix):
        raise ValueError('camera capture exact assignment differs')
    case = next((item for item in CASES if item.id == case_id[len(prefix):]), None)
    if case is None:
        raise ValueError('camera capture exact case missing')
    attempt = Path(attempt)
    if not attempt.is_dir() or not all((attempt / name).is_file()
                                       for name in ('construction.json', 'runner.py', 'config.json')):
        raise ValueError('materialized original Native attempt required')
    if any((attempt / name).exists() for name in ('history.jsonl', 'camera-frame-map.jsonl',
                                                  'comparison-context.json', 'capture-seal.json')):
        raise ValueError('refusing to overwrite original camera attempt')
    site = dict(packet['site'])
    site['site_sha256'] = _sha(Path(packet_path))
    reviewed_dir = attempt / 'reviewed-site'
    reviewed_dir.mkdir()
    shutil.copy2(packet_path, reviewed_dir / 'packet.json')
    copied_sources = []
    for item in packet['sources'].values():
        relative = Path(item['path'])
        destination = reviewed_dir / 'sources' / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source_root) / relative, destination)
        copied_sources.append(str(destination.relative_to(attempt)))
    built = None
    pipeline = None
    started = False
    completed = False
    try:
        built = build_case(adapter, site, case, body_length_m)
        if getattr(adapter, 'provenance', lambda: None)() == 'original_native':
            if not callable(getattr(adapter, 'pipeline_client', None)):
                raise ValueError('original Native adapter must supply PipelineCapture client')
            from pipeline_capture import PipelineCapture
            pipeline = PipelineCapture(adapter.pipeline_client(), built['ego'], attempt, case_id,
                                       required_observations=tuple(json.loads((attempt / 'config.json').read_text()).get('required_atoms', [])))
        if camera_lateral_offset_m:
            if not math.isfinite(camera_lateral_offset_m) or not 0 < camera_lateral_offset_m <= 1.0:
                raise ValueError('fallback camera lateral offset outside engineering range')
            adapter.start_cameras(attempt, site['camera_plan_sha256'], CAMERAS,
                                  lateral_offset_m=camera_lateral_offset_m)
        else:
            adapter.start_cameras(attempt, site['camera_plan_sha256'], CAMERAS)
        started = True
        mapping = []
        trace = []

        def record(row, index):
            camera_frames = adapter.record_camera_frame(row)
            if camera_frames != {name: index for name in CAMERAS}:
                raise ValueError('original camera frame index join differs')
            if pipeline is not None:
                captured = pipeline.capture(row['original_frame'], row['time_s'])
                if (captured.get('frame') != row['original_frame'] or
                        captured.get('time_s') != row['time_s'] or
                        captured.get('position_m') != row['ego_position_m']):
                    raise ValueError('original PipelineCapture/parking frame join differs')
            mapping.append({'original_frame': row['original_frame'],
                            'time_s': row['time_s'], 'camera_frames': camera_frames})
            position = row['ego_position_m']
            heading = row['ego_heading_deg']
            speed = row['ego_speed_mps']
            angle = math.radians(heading)
            trace.append({'frame': row['original_frame'], 'time_s': row['time_s'],
                          'position': dict(zip(('x', 'y', 'z'), position)),
                          'position_m': position, 'heading_deg': heading,
                          'speed_mps': speed, 'speed_mph': speed * 2.2369362921,
                          'velocity_mps': [speed * math.cos(angle),
                                           speed * math.sin(angle), 0.0]})

        history = capture_original_history(adapter, site, case,
                                           attempt / 'history.jsonl', frame_hook=record)
        if len(mapping) != 900:
            raise ValueError('original camera map incomplete')
        paths = adapter.finish_cameras()
        if not isinstance(paths, dict) or set(paths) != set(CAMERAS):
            raise ValueError('four original camera outputs missing')
        for name, path in paths.items():
            path = Path(path).resolve()
            if path != (attempt / (name + '.mkv')).resolve() or not path.is_file() or not path.stat().st_size:
                raise ValueError('original camera file missing: ' + name)
        if pipeline is not None:
            pipeline.close(confirmed=True)
        context = adapter.original_comparison_context()
        if not isinstance(context, dict):
            raise ValueError('original comparison context missing')
        expected = {'format': 'sidewalk-elevator-original-comparison-context',
                    'case_id': case_id, 'site_packet_sha256': site['site_sha256'],
                    'history_sha256': history['sha256'],
                    'ego_blueprint_sha256': site['ego_blueprint_sha256'],
                    'route_sha256': site['one_way_direction_sha256']}
        if any(context.get(key) != value for key, value in expected.items()) or not context.get('weather_sha256'):
            raise ValueError('original comparison context source differs')
        exception_key = {'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
                         'police_direction': 'police_direction_source_sha256',
                         'traffic_device_direction': 'traffic_device_source_sha256'}.get(case.exception)
        if context.get('exception_source_sha256') != (site.get(exception_key) if exception_key else None):
            raise ValueError('original comparison exception source differs')
        curb = context.get('curb_gap_target_m')
        if type(curb) not in (int, float) or not math.isfinite(curb) or curb < 0:
            raise ValueError('original comparison curb target missing')
        (attempt / 'camera-frame-map.jsonl').write_text(
            ''.join(json.dumps(item, sort_keys=True, allow_nan=False) + '\n' for item in mapping))
        (attempt / 'comparison-context.json').write_text(json.dumps(context, sort_keys=True, allow_nan=False) + '\n')
        if pipeline is None:
            (attempt / 'trace.jsonl').write_text(
                ''.join(json.dumps(item, sort_keys=True, allow_nan=False) + '\n' for item in trace))
        (attempt / 'video_frames.jsonl').write_text(
            ''.join(json.dumps({'video_frame': index, 'carla_frame': item['original_frame'],
                                'native_frame': item['original_frame'], 'time_s': item['time_s']},
                               sort_keys=True, allow_nan=False) + '\n'
                    for index, item in enumerate(mapping)))
        completed = True
        proof = {'case_id': case_id, 'site_packet_sha256': site['site_sha256'],
                'history_sha256': history['sha256'],
                'camera_frame_map_sha256': _sha(attempt / 'camera-frame-map.jsonl'),
                'comparison_context_sha256': _sha(attempt / 'comparison-context.json'),
                'camera_sha256': {name: _sha(Path(paths[name])) for name in CAMERAS},
                'frame_count': 900, 'full_video_decode': False,
                'physical_visibility_verified': False, 'legal_judgment': None}
    finally:
        if pipeline is not None and not pipeline.closed:
            pipeline.close(confirmed=False)
        if started and not completed:
            adapter.abort_cameras()
        if built is not None:
            for actor in reversed(built['owned']):
                adapter.destroy(actor)
    if adapter.restore_world() is not True:
        raise ValueError('original world restoration readback missing')
    source_names = ('history.jsonl', 'camera-frame-map.jsonl', 'comparison-context.json',
                    'trace.jsonl', 'video_frames.jsonl',
                    *(name + '.mkv' for name in CAMERAS),
                    'reviewed-site/packet.json', *copied_sources)
    if pipeline is not None:
        source_names += ('road.xodr', 'carla_recorder.log')
        source_names += tuple(str(path.relative_to(attempt)) for path in sorted((attempt / 'capture').rglob('*')) if path.is_file())
    seal = {'format': 'sidewalk-elevator-native-acquisition-seal',
            'case_id': case_id, 'site_packet_sha256': site['site_sha256'],
            'provenance_kind': 'native', 'diagnostic_fixture': False, 'frames': 900,
            'capture_rate_hz': 20,
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified'],
            'native_revision': {'construction_sha256': _sha(attempt / 'construction.json'),
                                'runner_sha256': _sha(attempt / 'runner.py')},
            'sources': {name: _sha(attempt / name) for name in source_names}}
    (attempt / 'capture-seal.json').write_text(json.dumps(seal, indent=2, sort_keys=True) + '\n')
    proof['capture_seal_sha256'] = _sha(attempt / 'capture-seal.json')
    return proof
