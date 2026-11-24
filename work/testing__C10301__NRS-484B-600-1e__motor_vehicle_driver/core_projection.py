"""Publish a sealed Native C10301 attempt as pinned Core input sources.

All graph bytes, OpenDRIVE and recorder text come from acquisition. The derived
trace/evidence keep the original frame and clock; this stage makes no physical
or legal acceptance claim.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from analysis import project_trace
from delivery_audit import audit_integrity


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def rows(path: Path):
    return [json.loads(line) for line in path.read_text().splitlines()
            if line.strip()]


def write_rows(path: Path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        for value in values:
            stream.write(json.dumps(value, allow_nan=False) + '\n')
    return sha(path)


def project(attempt: Path, destination: Path, case_id: str, *,
            allow_diagnostic=False) -> dict:
    attempt, destination = Path(attempt).resolve(), Path(destination).resolve()
    if destination.exists() or attempt == destination or attempt in destination.parents:
        raise ValueError('new separate Core source directory required')
    integrity = audit_integrity(attempt, case_id,
                                allow_diagnostic=allow_diagnostic)
    if integrity['diagnostic_fixture'] and not allow_diagnostic:
        raise ValueError('diagnostic Native source cannot publish production Core')
    road = attempt / 'road.xodr'
    recorder = attempt / 'recorder_info.txt'
    graph_map = attempt / 'graph-frame-readback.json'
    if any(not path.is_file() or path.is_symlink() for path in
           (road, recorder, graph_map)):
        raise ValueError('original Native Core source missing')
    recorder_log = attempt / 'carla_recorder.log'
    if (not integrity['diagnostic_fixture'] and
            (not recorder_log.is_file() or recorder_log.is_symlink() or
             not recorder_log.stat().st_size)):
        raise ValueError('original Native CARLA recorder log missing')
    trace = project_trace(attempt, case_id)
    graph_rows = json.loads(graph_map.read_text())['frames']
    camera_rows = json.loads((attempt / 'camera-frame-readback.json').read_text())['frames']
    world_rows = json.loads((attempt / 'world-frame-readback.json').read_text())['frames']
    control_rows = json.loads((attempt / 'control-frame-readback.json').read_text())['frames']
    if (len(trace) != len(graph_rows) or len(trace) != 900 or
            len(camera_rows) != len(trace) or len(world_rows) != len(trace) or
            len(control_rows) != len(trace)):
        raise ValueError('original Native Core frame coverage differs')
    actor_id = None
    evidence = []
    frame_index = []
    graphs = []
    for point, record, camera, world, control in zip(trace, graph_rows,
                                                     camera_rows, world_rows,
                                                     control_rows):
        frame, time_s = point['frame'], point['time_s']
        if (record.get('frame') != frame or record.get('time_s') != time_s or
                camera.get('frame') != frame or world.get('frame') != frame or
                control.get('frame') != frame or
                world.get('time_s') != time_s or
                world.get('no_rendering_mode') is not False):
            raise ValueError('original Native graph and motion clock differ')
        relative = record['adapter_graph']
        source = (attempt / relative).resolve()
        if (not source.is_file() or not source.is_relative_to(attempt) or
                sha(source) != record['sha256']):
            raise ValueError('original Native graph source changed')
        graph = json.loads(source.read_bytes())
        observed = graph.get('metadata', {}).get('observed_evidence')
        expected_rgb = [{'camera': name, 'frame': value,
                         'source': 'original_native_camera_readback'}
                        for name, value in camera['camera_frames'].items()]
        if (not isinstance(observed, dict) or
                observed.get('frame') != frame or
                observed.get('time_s') != time_s or
                observed.get('devices') != control.get('devices') or
                observed.get('control_actor_inventory') !=
                control.get('control_actor_inventory') or
                observed.get('world_settings') !=
                {'no_rendering_mode': False} or
                observed.get('rgb_sensors') != expected_rgb or
                not isinstance(observed.get('participants'), list)):
            raise ValueError('original Native graph observation packet differs')
        matches = [node for node in graph['nodes']
                   if node['attributes'].get('actor_id') is not None]
        if len(matches) != 1:
            raise ValueError('original Native graph subject identity differs')
        current = matches[0]['attributes']['actor_id']
        if type(current) is not int or current <= 0:
            raise ValueError('original Native graph actor ID invalid')
        if actor_id is None:
            actor_id = current
        if current != actor_id:
            raise ValueError('original Native graph actor changed')
        attributes = matches[0]['attributes']
        position = point['position_m']
        vertices = attributes.get('threedbbox')
        if (not isinstance(vertices, list) or len(vertices) != 8 or
                any(not isinstance(vertex, list) or len(vertex) != 3
                    for vertex in vertices)):
            raise ValueError('original Native graph body vertices missing')
        if ('vertex' in attributes and any(abs(a - b) > 1e-4
            for a, b in zip(attributes['vertex'], position))):
            raise ValueError('original Native graph and kinematics pose differ')
        evidence.append({
            'actor_id': actor_id, 'original_frame': frame,
            'recording_time_s': time_s, 'replay_frame': frame,
            'replay_simulation_time_s': time_s,
            'ego': {'position_m': position, 'speed_mps': point['speed_mps'],
                    'speed_provenance': 'original_trace_actor_get_velocity',
                    'heading_deg': point['heading_deg'],
                    'body_vertices_m': vertices},
            'original_observations': observed,
            'world': {'weather': {}}})
        graph_relative = 'graphs/abstract/' + f'{frame:08d}.adapter.json'
        frame_index.append({'frame': frame, 'simulation_time': time_s,
                            'adapter_graph': graph_relative})
        graphs.append((graph_relative, source))
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=destination.name + '.incomplete-',
                                  dir=destination.parent))
    try:
        trace_sha = write_rows(stage / 'trace.jsonl', trace)
        write_rows(stage / 'capture/evidence.jsonl', evidence)
        write_rows(stage / 'capture/native/frames.jsonl', frame_index)
        for relative, source in graphs:
            target = stage / 'capture/native' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        shutil.copyfile(road, stage / 'road.xodr')
        shutil.copyfile(recorder, stage / 'capture/recorder_info.txt')
        if recorder_log.is_file():
            shutil.copyfile(recorder_log, stage / 'carla_recorder.log')
        manifest = {
            'status': 'diagnostic' if integrity['diagnostic_fixture'] else 'original',
            'acquisition': 'original_live_run', 'case_id': case_id,
            'diagnostic_fixture': integrity['diagnostic_fixture'],
            'frames': len(trace), 'required_observations': [],
            'extraction_confirmed': True,
            'sources': {'road.xodr': sha(road), 'trace.jsonl': trace_sha},
            'observation_contract_version': 4,
            'physical_completion': False, 'legal_judgment': 'unresolved'}
        (stage / 'capture/manifest.json').write_text(
            json.dumps(manifest, indent=2) + '\n')
        receipt = {'format': 'c10301-core-sources-v1', 'case_id': case_id,
                   'diagnostic_fixture': integrity['diagnostic_fixture'],
                   'frames': len(trace),
                   'graph_inventory_sha256': sha(graph_map),
                   'road_sha256': sha(road), 'recorder_sha256': sha(recorder),
                   'trace_sha256': trace_sha,
                   'physical_completion': False,
                   'legal_judgment': 'unresolved'}
        (stage / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
        os.replace(stage, destination)
        return receipt
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise
