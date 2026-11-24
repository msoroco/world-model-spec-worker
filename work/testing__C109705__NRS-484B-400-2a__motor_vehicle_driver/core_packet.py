"""Project sealed approach samples into a diagnostic Core frame-join packet.

This is a software fixture bridge. It does not attest a Native recorder, a
public highway, or legal completion. Graph capture remains a separate source.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import tempfile
from pathlib import Path

from approach import _verified, measure
from native_capture import _checked_graph
from saved_delivery import FRAMES, audit_original_pixels


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _save(path: Path, rows: list[dict]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = ''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows).encode()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def project(attempt: Path, output: Path, actor_id: int = 7) -> dict:
    """Build a joined diagnostic packet from the saved, hash-checked sources."""
    attempt, output = Path(attempt), Path(output)
    if type(actor_id) is not int or actor_id <= 0:
        raise ValueError('positive diagnostic actor id required')
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite diagnostic Core packet')
    measured = measure(attempt)
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    if acquisition.get('diagnostic_fixture') is not True:
        raise ValueError('diagnostic bridge requires explicit diagnostic source')
    _, road_sha = _verified(attempt, 'road.xodr', acquisition)
    _, context_sha = _verified(attempt, 'intersection-context.json', acquisition)
    history_path, history_sha = _verified(attempt, 'approach-history.jsonl', acquisition)
    mapping_path, mapping_sha = _verified(attempt, 'video_frames.jsonl', acquisition)
    history, mapping = _rows(history_path), _rows(mapping_path)
    if len(history) != FRAMES or len(mapping) != FRAMES:
        raise ValueError('diagnostic Core packet requires complete original capture')
    graph_sources = []
    graph_manifest_sha = None
    if 'graph-frames.jsonl' in acquisition:
        graph_manifest_path, graph_manifest_sha = _verified(attempt, 'graph-frames.jsonl', acquisition)
        graph_rows = _rows(graph_manifest_path)
        if len(graph_rows) != FRAMES:
            raise ValueError('original adapter graph capture is incomplete')
        for index, (body, graph_row) in enumerate(zip(history, graph_rows)):
            frame, time_s = body['frame'], body['time_s']
            expected = f'graphs/abstract/{frame:08d}.adapter.json'
            if (graph_row.get('frame') != frame or
                    graph_row.get('adapter_graph') != expected or
                    graph_row.get('simulation_time') != time_s):
                raise ValueError('original adapter graph frame join differs')
            source = attempt / expected
            if source.is_symlink() or not source.is_file() or not source.resolve().is_relative_to(attempt.resolve()):
                raise ValueError('original adapter graph source missing or escaped')
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != graph_row.get('sha256'):
                raise ValueError('original adapter graph source hash differs')
            graph = _checked_graph(raw, frame, time_s)
            graph_actor_ids = [node['attributes'].get('actor_id')
                               for node in graph['nodes']
                               if node['attributes'].get('actor_id') is not None]
            if (len(graph_actor_ids) != 1 or type(graph_actor_ids[0]) is not int
                    or graph_actor_ids[0] != actor_id):
                raise ValueError('original adapter graph actor identity differs')
            graph_sources.append((index, raw))
    pixels = audit_original_pixels(attempt, acquisition['case_id'],
                                   allow_diagnostic=True)
    trace, evidence, frames = [], [], []
    previous = None
    for index, (body, view) in enumerate(zip(history, mapping)):
        frame, time_s = body['frame'], body['time_s']
        if (frame != view['carla_frame'] or view['video_frame'] != index or
                abs(time_s - view['time_s']) > 1e-6):
            raise ValueError('saved body/camera frame join differs')
        vertices = body['ego_body_vertices_xy_m']
        center = [sum(vertex[axis] for vertex in vertices) / len(vertices) for axis in (0, 1)]
        if previous is None:
            velocity = [0.0, 0.0, 0.0]
        else:
            dt = time_s - previous[1]
            if dt <= 0:
                raise ValueError('saved time did not advance')
            velocity = [(center[0] - previous[0][0]) / dt,
                        (center[1] - previous[0][1]) / dt, 0.0]
        previous = (center, time_s)
        speed = math.hypot(*velocity[:2])
        position = [*center, 0.0]
        observed = {'frame': frame, 'time_s': time_s,
                    'map_context': {'declared_public_way_road_ids': []},
                    'participants': []}
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': {'x': center[0], 'y': center[1], 'z': 0.0},
                      'position_m': position, 'heading_deg': math.degrees(body['ego_heading_rad']),
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': velocity, 'control': {}})
        evidence.append({'actor_id': actor_id, 'original_frame': frame,
                         'recording_time_s': time_s, 'replay_frame': frame,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': position, 'speed_mps': speed,
                                 'speed_provenance': 'synthetic_native_sample',
                                 'heading_deg': math.degrees(body['ego_heading_rad']),
                                 'body_vertices_m': [[x, y, z] for x, y in vertices for z in (0.0, 1.5)]},
                         'original_observations': observed, 'world': {'weather': {}}})
        frames.append({'frame': frame, 'simulation_time': time_s,
                       'adapter_graph': (f'graphs/abstract/{frame:08d}.adapter.json'
                                         if graph_sources else f'graphs/base/{index:08d}.adapter.json')})
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=output.name + '.incomplete-', dir=output.parent))
    try:
        hashes = {'trace.jsonl': _save(stage / 'trace.jsonl', trace),
                  'capture/evidence.jsonl': _save(stage / 'capture/evidence.jsonl', evidence),
                  'capture/native/frames.jsonl': _save(stage / 'capture/native/frames.jsonl', frames)}
        if graph_sources:
            for index, raw in graph_sources:
                target = stage / frames[index]['adapter_graph']
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(raw)
        receipt = {'kind': 'diagnostic_core_join_packet', 'case_id': acquisition['case_id'],
                   'source_sha256': {'road.xodr': road_sha,
                                     'intersection-context.json': context_sha,
                                     'approach-history.jsonl': history_sha,
                                     'video_frames.jsonl': mapping_sha},
                   'acquisition_sha256': hashlib.sha256((attempt / 'acquisition.json').read_bytes()).hexdigest(),
                   'generated_sha256': hashes, 'frames': len(trace),
                   'original_decoded_frames': pixels['decoded_frames'],
                   'original_media_sha256': pixels['media_sha256'],
                   'selected_measurement': measured['nearest_body_edge_range_m'],
                   'physical_completion': False, 'legal_judgment': 'unresolved',
                   'graph_capture_required': not bool(graph_sources)}
        if graph_manifest_sha:
            receipt['source_sha256']['graph-frames.jsonl'] = graph_manifest_sha
        (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        if output.exists() or output.is_symlink():
            raise ValueError('refusing to overwrite diagnostic Core packet')
        os.replace(stage, output)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
