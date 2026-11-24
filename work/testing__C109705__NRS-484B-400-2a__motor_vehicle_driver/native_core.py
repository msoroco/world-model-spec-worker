"""Project one hash-bound original Native attempt into a Core source packet.

This stage does not determine physical completion or any legal outcome. A
diagnostic source stays diagnostic even when the same publication path works.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from pathlib import Path

from approach import _verified
from native_capture import _checked_graph
from native_media import encode
from saved_delivery import CAMERAS, FRAMES, PRODUCTION_DIMENSIONS


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = ''.join(json.dumps(row, sort_keys=True, allow_nan=False,
                             separators=(',', ':')) + '\n' for row in rows).encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def project(attempt: Path, output: Path, *, allow_diagnostic=False,
            dimensions=None) -> dict:
    """Publish original velocity, graph, recorder and four camera sources.

    ``attempt`` remains unchanged. The destination must be new and separate.
    A diagnostic fixture requires explicit opt-in and is marked in the packet.
    """
    attempt, output = Path(attempt), Path(output)
    if output.exists() or output.is_symlink() or output.resolve() == attempt.resolve():
        raise ValueError('new separate Core packet output required')
    acquisition = json.loads((attempt / 'acquisition.json').read_text())
    diagnostic = acquisition.get('diagnostic_fixture') is not False
    if diagnostic and not allow_diagnostic:
        raise ValueError('diagnostic original Native source cannot publish production Core')
    names = ('road.xodr', 'approach-history.jsonl', 'body_history.jsonl',
             'video_frames.jsonl', 'graph-frames.jsonl',
             'synchronized_motion_records.jsonl', 'control_actor_inventory.jsonl',
             'recorder_info.txt', 'carla_recorder.log')
    sources = {name: _verified(attempt, name, acquisition)[0] for name in names}
    history = _rows(sources['approach-history.jsonl'])
    bodies = _rows(sources['body_history.jsonl'])
    views = _rows(sources['video_frames.jsonl'])
    graphs = _rows(sources['graph-frames.jsonl'])
    motions = _rows(sources['synchronized_motion_records.jsonl'])
    controls = _rows(sources['control_actor_inventory.jsonl'])
    if any(len(rows) != FRAMES for rows in
           (history, bodies, views, graphs, motions, controls)):
        raise ValueError('original Native Core source coverage incomplete')
    if not re.search(r'\bCreate \d+: \S+', sources['recorder_info.txt'].read_text()):
        raise ValueError('original CARLA recorder actor census missing')
    if dimensions is None:
        dimensions = {name: tuple(PRODUCTION_DIMENSIONS[name]) for name in CAMERAS}
    if not diagnostic and dimensions != {
            name: tuple(PRODUCTION_DIMENSIONS[name]) for name in CAMERAS}:
        raise ValueError('production camera dimensions differ')
    trace, evidence, frame_index, graph_sources = [], [], [], []
    actor_id = None
    for index, (row, body, view, graph_row, motion, control) in enumerate(
            zip(history, bodies, views, graphs, motions, controls)):
        frame, time_s = row['frame'], row['time_s']
        if (type(frame) is not int or type(time_s) not in (int, float) or
                not math.isfinite(time_s) or
                any(value.get('frame') != frame for value in
                    (body, view, graph_row, control)) or
                body.get('time_s') != time_s or view.get('time_s') != time_s or
                control.get('time_s') != time_s or motion.get('time_s') != time_s or
                motion.get('value', {}).get('frame') != frame or
                graph_row.get('simulation_time') != time_s or
                view.get('video_frame') != index):
            raise ValueError('original Native Core frame/time join differs')
        relative = f'graphs/abstract/{frame:08d}.adapter.json'
        if graph_row.get('adapter_graph') != relative:
            raise ValueError('original Native Core graph inventory differs')
        graph_source = attempt / relative
        if (graph_source.is_symlink() or not graph_source.is_file() or
                not graph_source.resolve().is_relative_to(attempt.resolve()) or
                _sha(graph_source) != graph_row.get('sha256')):
            raise ValueError('original Native Core graph source differs')
        graph = _checked_graph(graph_source.read_bytes(), frame, time_s)
        ids = [node['attributes'].get('actor_id') for node in graph['nodes']
               if node['attributes'].get('actor_id') is not None]
        if len(ids) != 1 or type(ids[0]) is not int or ids[0] <= 0:
            raise ValueError('original Native Core subject identity differs')
        if actor_id is None:
            actor_id = ids[0]
        if ids[0] != actor_id:
            raise ValueError('original Native Core subject changed')
        participants = list(motion['value'].values())
        participants = [item for item in participants if isinstance(item, dict)]
        if not any(item.get('actor_id') == actor_id for item in participants):
            raise ValueError('original Native Core subject motion missing')
        observed = {**control, 'participants': participants}
        if graph['metadata'].get('observed_evidence') != observed:
            raise ValueError('original Native Core graph observation differs')
        vertices = body.get('body_vertices_m')
        velocity = body.get('velocity_mps')
        if (body.get('velocity_source') != 'original_trace_actor_get_velocity' or
                not isinstance(vertices, list) or len(vertices) < 4 or
                not isinstance(velocity, list) or len(velocity) != 3 or
                any(type(v) not in (int, float) or not math.isfinite(v)
                    for v in velocity)):
            raise ValueError('original Native Core body/velocity missing')
        position = [sum(vertex[axis] for vertex in vertices) / len(vertices)
                    for axis in range(3)]
        speed = math.sqrt(sum(value * value for value in velocity))
        heading = math.degrees(row['ego_heading_rad'])
        trace.append({'frame': frame, 'time_s': time_s,
                      'position': dict(zip(('x', 'y', 'z'), position)),
                      'position_m': position, 'heading_deg': heading,
                      'speed_mps': speed, 'speed_mph': speed / .44704,
                      'velocity_mps': velocity, 'control': {}})
        evidence.append({'actor_id': actor_id, 'original_frame': frame,
                         'recording_time_s': time_s, 'replay_frame': frame,
                         'replay_simulation_time_s': time_s,
                         'ego': {'position_m': position, 'speed_mps': speed,
                                 'speed_provenance': 'original_trace_actor_get_velocity',
                                 'heading_deg': heading,
                                 'body_vertices_m': vertices},
                         'original_observations': observed,
                         'world': {'weather': {}}})
        frame_index.append({'frame': frame, 'simulation_time': time_s,
                            'adapter_graph': relative})
        graph_sources.append((relative, graph_source))
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=output.name + '.incomplete-',
                                 dir=output.parent))
    try:
        trace_hash = _write_rows(stage / 'trace.jsonl', trace)
        _write_rows(stage / 'capture/evidence.jsonl', evidence)
        _write_rows(stage / 'capture/native/frames.jsonl', frame_index)
        for relative, source in graph_sources:
            target = stage / 'capture/native' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for name, target in [('road.xodr', 'road.xodr'),
                             ('recorder_info.txt', 'capture/recorder_info.txt'),
                             ('carla_recorder.log', 'carla_recorder.log'),
                             ('synchronized_motion_records.jsonl',
                              'synchronized_motion_records.jsonl')]:
            destination = stage / target
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sources[name], destination)
        manifest = {
            'status': 'diagnostic' if diagnostic else 'original',
            'acquisition': 'original_live_run',
            'diagnostic_fixture': diagnostic,
            'case_id': acquisition['case_id'],
            'source_run': _sha(attempt / 'acquisition.json'),
            'map': acquisition['map_binding']['map_name'],
            'frames': FRAMES, 'required_observations': [],
            'extraction_confirmed': True,
            'sources': {'road.xodr': _sha(stage / 'road.xodr'),
                        'trace.jsonl': trace_hash},
            'observation_contract_version': 5,
            'physical_completion': False,
            'legal_judgment': 'unresolved'}
        (stage / 'capture/manifest.json').write_text(
            json.dumps(manifest, indent=2, allow_nan=False) + '\n')
        media = encode(attempt, stage, dimensions)
        receipt = {'kind': 'original_native_core_packet',
                   'diagnostic_fixture': diagnostic,
                   'case_id': acquisition['case_id'],
                   'frames': FRAMES, 'source_sha256':
                   {name: _sha(source) for name, source in sources.items()},
                   'trace_sha256': trace_hash, 'media': media,
                   'physical_completion': False,
                   'legal_judgment': 'unresolved'}
        (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        if output.exists() or output.is_symlink():
            raise ValueError('refusing to overwrite Core packet')
        os.replace(stage, output)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
