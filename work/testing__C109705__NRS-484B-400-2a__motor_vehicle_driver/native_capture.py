"""Collect a source-bound 45-second Native left-turn attempt.

The injected adapter owns CARLA actors and camera sensors. Each camera callback
must provide the original PNG bytes for the same simulator frame as the ego row.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path

from approach import measure
from native_map import verify_live_map
from saved_delivery import CAMERAS, FRAMES, PREFIX, SUFFIXES, audit_original_pixels


def _checked_graph(raw: bytes, frame: int, time_s: float) -> dict:
    """Validate the original adapter graph envelope before retaining its bytes."""
    if not isinstance(raw, bytes):
        raise ValueError('Native adapter graph bytes missing')
    try:
        graph = json.loads(raw, parse_constant=lambda value: (_ for _ in ()).throw(
            ValueError('Nonfinite Native graph value: ' + value)))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Native adapter graph is not JSON') from exc
    graph_time = graph.get('metadata', {}).get('simulation_time_s') if isinstance(graph, dict) and isinstance(graph.get('metadata'), dict) else None
    if (not isinstance(graph, dict) or graph.get('format') != 'native-adapter-graph-v1'
            or not isinstance(graph.get('metadata'), dict)
            or graph['metadata'].get('frame') != frame
            or type(graph_time) not in (int, float) or not math.isfinite(graph_time)
            or abs(graph_time - time_s) > .001
            or not isinstance(graph.get('nodes'), list) or not graph['nodes']
            or not isinstance(graph.get('edges'), list)):
        raise ValueError('Native adapter graph frame, time or structure differs')
    if any(not isinstance(node, dict) or type(node.get('id')) not in (str, int) or
           not isinstance(node.get('attributes'), dict) for node in graph['nodes']):
        raise ValueError('Native adapter graph node malformed')
    if len({node['id'] for node in graph['nodes']}) != len(graph['nodes']):
        raise ValueError('Native adapter graph node identity duplicated')
    if any(not isinstance(edge, dict) or type(edge.get('source')) is not int
           or type(edge.get('target')) is not int
           or not 0 <= edge['source'] < len(graph['nodes'])
           or not 0 <= edge['target'] < len(graph['nodes'])
           or not isinstance(edge.get('attributes'), dict)
           for edge in graph['edges']):
        raise ValueError('Native adapter graph edge malformed')
    return graph


def _write_jsonl(path: Path, rows: list[dict]) -> str:
    raw = ''.join(json.dumps(row, sort_keys=True, separators=(',', ':')) + '\n'
                  for row in rows).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def capture(adapter, case_id: str, map_packet_path: Path, output_root: Path) -> dict:
    """Capture exact frame identities and original camera PNGs from an adapter.

    ``adapter`` exposes world, start(plan), tick(), read_ego(frame),
    read_cameras(frame), brake(), and cleanup(). The capture rejects missing
    callbacks, frame gaps, cadence drift, and malformed original PNG headers.
    Each camera callback supplies its own Native presentation time.
    """
    if case_id not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError('unknown exact approach case')
    binding = verify_live_map(adapter.world, map_packet_path, case_id)
    survey_bytes = Path(map_packet_path).read_bytes()
    if hashlib.sha256(survey_bytes).hexdigest() != binding['survey_packet_sha256']:
        raise ValueError('Native survey packet changed before capture')
    packet = json.loads(survey_bytes)
    review_bytes = None
    if binding['public_highway_reviewed']:
        source = packet['public_highway_review']['source']
        base = Path(map_packet_path).parent.resolve()
        review_path = (base / source['path']).resolve()
        if (not review_path.is_relative_to(base) or not review_path.is_file() or
                review_path.is_symlink()):
            raise ValueError('reviewed public-highway source missing or escaped')
        review_bytes = review_path.read_bytes()
        if hashlib.sha256(review_bytes).hexdigest() != source['sha256']:
            raise ValueError('reviewed public-highway source changed before capture')
    destination = Path(output_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Native attempt destination already exists')
    root = Path(tempfile.mkdtemp(prefix=destination.name + '.incomplete-',
                                 dir=destination.parent))
    started = False
    opendrive = None
    history: list[dict] = []
    body_history: list[dict] = []
    participants_history: list[dict] = []
    frame_map: list[dict] = []
    graph_map: list[dict] = []
    archives = {}
    recorder_active = False
    recorder_info = None
    try:
        adapter.start(binding['planned_construction'])
        started = True
        if getattr(adapter, 'native_attested', False):
            start_recorder = getattr(adapter, 'start_recorder', None)
            if callable(start_recorder):
                start_recorder(root / 'carla_recorder.log')
                recorder_active = True
        archives = {name: zipfile.ZipFile(root / (name + '.zip'), 'w',
                                         compression=zipfile.ZIP_STORED)
                    for name in sorted(CAMERAS)}
        for index in range(FRAMES):
            tick = adapter.tick()
            frame, time_s = tick['frame'], tick['time_s']
            if type(frame) is not int or type(time_s) not in (int, float) or not math.isfinite(time_s):
                raise ValueError('Native frame identity missing')
            if history and (frame != history[-1]['frame'] + 1 or
                            abs(time_s - history[-1]['time_s'] - .05) > .001):
                raise ValueError('Native frame gap or cadence drift')
            ego = adapter.read_ego(frame)
            if ego.get('frame') != frame or ego.get('case_id') != case_id:
                raise ValueError('Native ego frame/case readback differs')
            row = {**ego, 'frame': frame, 'time_s': time_s}
            history.append(row)
            read_body = getattr(adapter, 'read_body', None)
            if callable(read_body):
                physical = read_body(frame)
                if not isinstance(physical, dict) or physical.get('frame') != frame:
                    raise ValueError('Native full body frame identity missing')
                vertices = physical.get('body_vertices_m')
                if (physical.get('road_id') != row.get('road_id') or
                        not isinstance(vertices, list) or len(vertices) < 4 or
                        any(not isinstance(vertex, list) or len(vertex) < 3 or
                            any(type(value) not in (int, float) or not math.isfinite(value)
                                for value in vertex[:3]) for vertex in vertices) or
                        [vertex[:2] for vertex in vertices] != row.get('ego_body_vertices_xy_m')):
                    raise ValueError('Native full body geometry differs from approach source')
                if getattr(adapter, 'native_attested', False):
                    velocity = physical.get('velocity_mps')
                    if (physical.get('velocity_source') != 'original_trace_actor_get_velocity'
                            or not isinstance(velocity, list) or len(velocity) != 3
                            or any(type(value) not in (int, float) or not math.isfinite(value)
                                   for value in velocity)):
                        raise ValueError('original Native actor velocity source missing')
                body_history.append({**physical, 'frame': frame, 'time_s': time_s})
            read_participants = getattr(adapter, 'read_participants', None)
            if callable(read_participants):
                participants = read_participants(frame)
                actor_id = getattr(getattr(adapter, 'ego_actor', None), 'id', None)
                if (not isinstance(participants, list) or not participants or
                        len({p.get('actor_id') for p in participants if isinstance(p, dict)}) != len(participants) or
                        sum(isinstance(p, dict) and p.get('actor_id') == actor_id
                            for p in participants) != 1):
                    raise ValueError('Native participant identities differ from owned ego')
                ego_participant = next(p for p in participants
                                       if p['actor_id'] == actor_id)
                if (not body_history or
                        ego_participant.get('body_vertices_m') != body_history[-1]['body_vertices_m'] or
                        ego_participant.get('velocity_mps') != body_history[-1]['velocity_mps']):
                    raise ValueError('Native participant body or velocity join differs')
                participants_history.append({'time_s': time_s,
                    'value': {'frame': frame, **{str(p['actor_id']): p for p in participants}}})
            camera_rows = adapter.read_cameras(frame)
            if not isinstance(camera_rows, dict) or set(camera_rows) != CAMERAS:
                raise ValueError('Native four-camera callback set missing')
            camera_times = {}
            for name in sorted(CAMERAS):
                camera = camera_rows[name]
                raw = camera.get('png')
                if (camera.get('frame') != frame or not isinstance(raw, bytes) or
                        len(raw) < 16 or not raw.startswith(b'\x89PNG\r\n\x1a\n')):
                    raise ValueError('Native original camera PNG/frame missing: ' + name)
                camera_time = camera.get('time_s')
                if (type(camera_time) not in (int, float) or
                        not math.isfinite(camera_time) or
                        abs(camera_time - time_s) > .001):
                    raise ValueError('Native original camera timestamp drift: ' + name)
                camera_times[name] = camera_time
                archives[name].writestr(f'{index:04d}-{frame}.png', raw)
            frame_map.append({'frame': frame, 'video_frame': index,
                              'carla_frame': frame, 'native_frame': frame,
                              'time_s': time_s,
                              'camera_frames': {name: frame for name in sorted(CAMERAS)},
                              'camera_times_s': camera_times})
            read_graph = getattr(adapter, 'read_graph', None)
            if read_graph is None:
                if getattr(adapter, 'native_attested', False):
                    ego_actor = getattr(adapter, 'ego_actor', None)
                    if ego_actor is None:
                        raise ValueError('Attested Native capture requires original adapter graph')
                    from original_graph import collect
                    graph_raw = collect(adapter.world, ego_actor,
                                        adapter.world.get_snapshot(),
                                        expected_frame=frame,
                                        expected_time_s=time_s)
                else:
                    graph_raw = None
            else:
                graph_raw = read_graph(frame)
            if graph_raw is not None:
                _checked_graph(graph_raw, frame, time_s)
                graph_path = root / 'graphs/abstract' / f'{frame:08d}.adapter.json'
                graph_path.parent.mkdir(parents=True, exist_ok=True)
                graph_path.write_bytes(graph_raw)
                graph_map.append({'frame': frame, 'simulation_time': time_s,
                                  'adapter_graph': graph_path.relative_to(root).as_posix(),
                                  'sha256': hashlib.sha256(graph_raw).hexdigest()})
        opendrive = adapter.world.get_map().to_opendrive()
        if graph_map and len(graph_map) != FRAMES:
            raise ValueError('Native adapter graph capture is incomplete')
        if body_history and len(body_history) != FRAMES:
            raise ValueError('Native full body capture is incomplete')
        if participants_history and len(participants_history) != FRAMES:
            raise ValueError('Native participant capture is incomplete')
        read_geometry = getattr(adapter, 'read_road_geometry', None)
        geometry = read_geometry() if callable(read_geometry) else None
        if geometry is not None and not isinstance(geometry, dict):
            raise ValueError('Native road geometry is not an object')
        if (not isinstance(opendrive, str) or
                hashlib.sha256(opendrive.encode()).hexdigest() != binding['opendrive_sha256']):
            raise ValueError('Native OpenDRIVE changed during capture')
    except BaseException:
        try:
            if recorder_active:
                adapter.stop_recorder()
                recorder_active = False
        finally:
            shutil.rmtree(root, ignore_errors=True)
        raise
    finally:
        try:
            for archive in archives.values():
                archive.close()
            try:
                if recorder_active:
                    recorder_info = adapter.stop_recorder()
                    recorder_active = False
                if started:
                    adapter.brake()
            finally:
                adapter.cleanup()
        except BaseException:
            shutil.rmtree(root, ignore_errors=True)
            raise
    try:
        context = binding['intersection_context']
        road_bytes = opendrive.encode()
        (root / 'road.xodr').write_bytes(road_bytes)
        context_bytes = (json.dumps(context, sort_keys=True, separators=(',', ':')) + '\n').encode()
        (root / 'intersection-context.json').write_bytes(context_bytes)
        hashes = {'road.xodr': hashlib.sha256(road_bytes).hexdigest(),
                  'intersection-context.json': hashlib.sha256(context_bytes).hexdigest(),
                  'approach-history.jsonl': _write_jsonl(root / 'approach-history.jsonl', history),
                  'video_frames.jsonl': _write_jsonl(root / 'video_frames.jsonl', frame_map)}
        (root / 'survey-packet.json').write_bytes(survey_bytes)
        hashes['survey-packet.json'] = hashlib.sha256(survey_bytes).hexdigest()
        if review_bytes is not None:
            (root / 'public-highway-review-source').write_bytes(review_bytes)
            hashes['public-highway-review-source'] = hashlib.sha256(review_bytes).hexdigest()
        if body_history:
            hashes['body_history.jsonl'] = _write_jsonl(root / 'body_history.jsonl', body_history)
        if participants_history:
            hashes['synchronized_motion_records.jsonl'] = _write_jsonl(
                root / 'synchronized_motion_records.jsonl', participants_history)
        if recorder_info is not None:
            info_bytes = recorder_info.encode()
            (root / 'recorder_info.txt').write_bytes(info_bytes)
            hashes['recorder_info.txt'] = hashlib.sha256(info_bytes).hexdigest()
            recorder_path = root / 'carla_recorder.log'
            hashes['carla_recorder.log'] = hashlib.sha256(
                recorder_path.read_bytes()).hexdigest()
        if geometry is not None:
            geometry_bytes = (json.dumps(geometry, sort_keys=True, separators=(',', ':')) + '\n').encode()
            (root / 'road_geometry.json').write_bytes(geometry_bytes)
            hashes['road_geometry.json'] = hashlib.sha256(geometry_bytes).hexdigest()
        if graph_map:
            hashes['graph-frames.jsonl'] = _write_jsonl(root / 'graph-frames.jsonl', graph_map)
        complete_source = (getattr(adapter, 'native_attested', False) and
                           binding['public_highway_reviewed'] is True and
                           len(body_history) == FRAMES and geometry is not None and
                           len(graph_map) == FRAMES and
                           len(participants_history) == FRAMES and
                           recorder_info is not None)
        acquisition = {'case_id': case_id,
                       'diagnostic_fixture': not complete_source,
                       'map_binding': binding,
                       'media': {name: {'kind': 'original_native', 'path': name + '.zip',
                                        'sha256': hashlib.sha256((root / (name + '.zip')).read_bytes()).hexdigest()}
                                 for name in sorted(CAMERAS)}}
        acquisition.update({name: {'kind': 'original_native', 'sha256': digest}
                            for name, digest in hashes.items()})
        (root / 'acquisition.json').write_text(json.dumps(acquisition, indent=2) + '\n')
        measured = measure(root)
        pixels = audit_original_pixels(root, case_id,
                                       allow_diagnostic=acquisition['diagnostic_fixture'])
        os.replace(root, destination)
        return {'case_id': case_id, 'frame_count': FRAMES, 'source_sha256': hashes,
                'approach_measurement': measured, 'decoded_frames': pixels['decoded_frames'],
                'physical_completion': False, 'legal_judgment': 'unresolved'}
    except BaseException:
        shutil.rmtree(root, ignore_errors=True)
        raise
