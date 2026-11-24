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
    trace = project_trace(attempt, case_id)
    graph_rows = json.loads(graph_map.read_text())['frames']
    if len(trace) != len(graph_rows) or len(trace) != 900:
        raise ValueError('original Native Core frame coverage differs')
    actor_id = None
    evidence = []
    frame_index = []
    graphs = []
    for point, record in zip(trace, graph_rows):
        frame, time_s = point['frame'], point['time_s']
        if record.get('frame') != frame or record.get('time_s') != time_s:
            raise ValueError('original Native graph and motion clock differ')
        relative = record['adapter_graph']
        source = (attempt / relative).resolve()
        if (not source.is_file() or not source.is_relative_to(attempt) or
                sha(source) != record['sha256']):
            raise ValueError('original Native graph source changed')
        graph = json.loads(source.read_bytes())
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
        if ('vertex' in attributes and any(abs(a - b) > 1e-4
            for a, b in zip(attributes['vertex'], position))):
            raise ValueError('original Native graph and kinematics pose differ')
        evidence.append({
            'actor_id': actor_id, 'original_frame': frame,
            'recording_time_s': time_s, 'replay_frame': frame,
            'replay_simulation_time_s': time_s,
            'ego': {'position_m': position, 'speed_mps': point['speed_mps'],
                    'speed_provenance': 'original_trace_actor_get_velocity',
                    'heading_deg': point['heading_deg']},
            'original_observations': {}, 'world': {'weather': {}}})
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
