"""Lazy Native capture contract for the four exact departure cases.

The caller supplies a CARLA adapter; importing this module does not import CARLA.
All packet fields come from adapter readback, rather than requested targets.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('departure_route_policy', HERE / 'construction.py')
route_policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(route_policy)

CAMERAS = ('dash', 'front', 'left', 'right')


def _point(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f'{name} must be an xy pair')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in value):
        raise ValueError(f'{name} must be finite')
    return [float(value[0]), float(value[1])]


def _state(raw, frame, previous_frame, expected_case):
    if raw.get('case_id') != expected_case:
        raise ValueError('Native ego case readback differs')
    if raw.get('frame') != frame or frame != previous_frame + 1:
        raise ValueError('Native ego frame gap or mismatch')
    position = _point(raw.get('position_xy_m'), 'ego position')
    corners = raw.get('body_corners_xy_m')
    if not isinstance(corners, list) or len(corners) < 4:
        raise ValueError('Native full body corners missing')
    corners = [_point(c, 'body corner') for c in corners]
    heading, speed = raw.get('heading_rad'), raw.get('speed_mps')
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in (heading, speed)) or speed < 0:
        raise ValueError('Native heading or speed invalid')
    phase = raw.get('phase')
    if phase not in ('approach', 'intersection_entry', 'turning', 'departure'):
        raise ValueError('Native route phase missing')
    if not isinstance(raw.get('road_id'), (str, int)):
        raise ValueError('Native road ID missing')
    if raw.get('driver_control') is not True:
        raise ValueError('Native driver control missing')
    elapsed = raw.get('elapsed_seconds')
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError('Native original elapsed clock missing')
    return {'frame': frame, 'phase': phase, 'road_id': raw['road_id'],
            'position_xy_m': position, 'body_corners_xy_m': corners,
            'heading_rad': float(heading), 'speed_mps': float(speed),
            'elapsed_seconds': float(elapsed)}


def capture(adapter, case_id, survey, map_source_path, output_dir, *, camera_source=None):
    """Execute a 45 s, 20 Hz capture using an injected synchronous Native adapter.

    Adapter methods: spawn_ego, configure_cameras, resolve_waypoint, apply_control,
    tick, ego_snapshot, camera_frame, emergency_stop, destroy. A camera_frame
    returns metadata for an original retained frame with its source path; it may
    not substitute a generated image or an absent frame.
    """
    plan = route_policy.build(case_id, survey, map_source_path=map_source_path)
    if tuple(plan['camera_plan']) != CAMERAS:
        raise ValueError('four exact camera channels required')
    output = Path(output_dir)
    if output.is_symlink():
        raise ValueError('refusing symlinked Native capture')
    for name in ('original-trace.json', 'original-camera-index.json',
                 'original-cameras', 'original-map.xodr',
                 'original-map-packet.json', 'source-manifest.json',
                 'original-bindings.json', 'acquisition.json',
                 'capture-seal.json', 'trace.jsonl', 'video_frames.jsonl',
                 'graphs', 'graph-frames.jsonl'):
        if (output / name).exists() or (output / name).is_symlink():
            raise ValueError('refusing to overwrite original Native capture')
    if camera_source is not None and Path(camera_source.output).resolve().parent != output.resolve():
        raise ValueError('original camera sources must be attempt local')
    output.mkdir(parents=True, exist_ok=True)
    ego = None
    samples = []
    cameras = {name: [] for name in CAMERAS}
    graph_index = []
    previous_frame = None
    waypoint_index = 0
    entered = departed = False
    try:
        ego = adapter.spawn_ego(plan['ego_blueprint_id'], survey['map_name'], case_id)
        if camera_source is None:
            adapter.configure_cameras(ego, CAMERAS, fps=20)
        else:
            camera_source.configure_cameras(ego, CAMERAS, fps=20)
        for tick_index in range(900):
            waypoint_ids = plan['left_turn_route_waypoint_ids']
            if waypoint_index < len(waypoint_ids):
                target = _point(adapter.resolve_waypoint(waypoint_ids[waypoint_index]), 'Native waypoint')
            else:
                target = plan['departure_target_xy_m']
            if samples:
                prior = samples[-1]
                command = route_policy.control(prior['position_xy_m'], prior['heading_rad'], target,
                                               prior['speed_mps'])
            else:
                command = {'throttle': 0.0, 'brake': 1.0, 'steer': 0.0}
            adapter.apply_control(ego, command)
            frame = adapter.tick()
            if type(frame) is not int or (previous_frame is not None and frame != previous_frame + 1):
                raise ValueError('Native tick frame discontinuity')
            raw = adapter.ego_snapshot(ego, frame)
            sample = _state(raw, frame, previous_frame if previous_frame is not None else frame - 1, case_id)
            if samples and abs(sample['elapsed_seconds'] - samples[0]['elapsed_seconds'] - tick_index / 20) > 0.002:
                raise ValueError('Native original 20 Hz clock drift')
            if sample['phase'] == 'turning' and not entered:
                raise ValueError('Native turn began before observed intersection entry')
            if sample['phase'] == 'intersection_entry':
                if departed:
                    raise ValueError('Native route returned to intersection after departure')
                entered = True
            if sample['phase'] == 'departure':
                if not entered or sample['road_id'] != survey['destination_road_id']:
                    raise ValueError('departure lacks observed entry or destination road')
                departed = True
            if sample['phase'] != 'departure' and departed:
                raise ValueError('Native route regressed after departure')
            samples.append(sample)
            for name in CAMERAS:
                camera = (adapter.camera_frame(name, frame) if camera_source is None
                          else camera_source.camera_frame(name, frame))
                if not isinstance(camera, dict) or camera.get('frame') != frame or camera.get('channel') != name:
                    raise ValueError('Native four-camera frame missing or unsynchronized')
                if not camera.get('source_path') or not camera.get('source_sha256'):
                    raise ValueError('Native camera source binding missing')
                cameras[name].append(camera)
            if getattr(adapter, 'world', None) is not None:
                from original_graph import collect
                snapshot = adapter.world.get_snapshot()
                raw_graph = collect(adapter.world, ego, snapshot,
                                    expected_frame=frame,
                                    expected_time_s=sample['elapsed_seconds'])
                graph_path = output / 'graphs/abstract' / f'{frame:08d}.adapter.json'
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                with graph_path.open('xb') as stream:
                    stream.write(raw_graph)
                graph_index.append({'frame': frame,
                                    'simulation_time': sample['elapsed_seconds'],
                                    'adapter_graph': str(graph_path.relative_to(output)),
                                    'sha256': hashlib.sha256(raw_graph).hexdigest()})
            if math.dist(sample['position_xy_m'], target) < 0.5 and waypoint_index < len(waypoint_ids):
                waypoint_index += 1
            previous_frame = frame
        if not entered or not departed:
            raise ValueError('Native original trace lacks intersection entry or departure')
        if math.dist(samples[0]['position_xy_m'], samples[-1]['position_xy_m']) < 3:
            raise ValueError('Native ego did not move through turn')
        packet = {'case_id': case_id, 'approach_road_id': survey['approach_road_id'],
                  'destination_road_id': survey['destination_road_id'], 'maneuver': 'left_turn',
                  'driver_control': True, 'rate_hz': 20, 'samples': samples}
        trace_path = output / 'original-trace.json'
        with trace_path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(packet, indent=2) + '\n')
        camera_path = output / 'original-camera-index.json'
        with camera_path.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps({'case_id': case_id, 'channels': cameras}, indent=2) + '\n')
        if getattr(adapter, 'world', None) is not None:
            if len(graph_index) != 900:
                raise ValueError('original Native graph capture incomplete')
            with (output / 'graph-frames.jsonl').open('x', encoding='utf-8') as stream:
                for graph in graph_index:
                    stream.write(json.dumps(graph, allow_nan=False) + '\n')
        return {'case_id': case_id, 'trace_path': str(trace_path),
                'trace_sha256': hashlib.sha256(trace_path.read_bytes()).hexdigest(),
                'camera_index_path': str(camera_path),
                'camera_index_sha256': hashlib.sha256(camera_path.read_bytes()).hexdigest(),
                'map_source_sha256': plan['survey_source_sha256'], 'frames': len(samples),
                'physical_acceptance_claimed': False}
    finally:
        try:
            if camera_source is not None:
                camera_source.close()
        finally:
            if ego is not None:
                try:
                    adapter.emergency_stop(ego)
                finally:
                    adapter.destroy(ego)
