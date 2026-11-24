"""Independent exact-case saved Native departure and media audit.

Diagnostic fixtures exercise the gates but never yield delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from saved_delivery import ASSIGNMENT, SUFFIXES, audit as audit_saved


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def audit(attempt, case_id, *, allow_diagnostic=False):
    root = Path(attempt).resolve()
    if case_id not in {ASSIGNMENT + '__' + name for name in SUFFIXES}:
        raise ValueError('wrong exact delivery case')
    manifest_path = root / 'source-manifest.json'
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise ValueError('Missing required source: source-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    diagnostic = manifest.get('acquisition_kind') == 'diagnostic_fixture'
    if diagnostic and not allow_diagnostic:
        raise ValueError('diagnostic source cannot be delivery accepted')
    saved = audit_saved(root, manifest, case_id=case_id,
                        allow_diagnostic=allow_diagnostic)
    if saved['source_integrity'] != 'passed' or not saved['actual_pixels'] or not saved['full_source_decode']:
        raise ValueError('original source pixel integrity incomplete')
    frame_map = _rows(root / 'video_frames.jsonl')
    body = _rows(root / 'body_history.jsonl')
    if len(frame_map) != 900 or len(body) != 900:
        raise ValueError('original body and frame coverage differs')
    for index, (row, frame) in enumerate(zip(body, frame_map)):
        if (row['frame'] != frame['carla_frame'] or frame['video_frame'] != index or
                abs(row['time_s'] - frame['time_s']) > 1e-4):
            raise ValueError('original body and camera time join differs')
    from scenario_pipeline.worker_exchange.native_output import assess_left_turn
    physical = assess_left_turn(root)
    if physical['status'] != 'met' or not physical.get('observed') or not physical.get('sources'):
        raise ValueError('original physical completion not established: ' + physical['status'])
    inventory = _rows(root / 'graph-frames.jsonl')
    if len(inventory) != 900:
        raise ValueError('all-participant graph coverage incomplete')
    ego_id = None
    for row, frame in zip(inventory, frame_map):
        name = row.get('adapter_graph')
        if not isinstance(name, str) or Path(name).is_absolute() or '..' in Path(name).parts:
            raise ValueError('original graph source path invalid')
        source = (root / name).resolve()
        if (not source.is_relative_to(root) or not source.is_file() or source.is_symlink()
                or _sha(source) != row.get('sha256')):
            raise ValueError('original graph source changed')
        graph = json.loads(source.read_text())
        meta = graph.get('metadata', {})
        if (graph.get('format') != 'native-adapter-graph-v1' or
                row.get('frame') != frame['carla_frame'] or
                meta.get('frame') != frame['carla_frame'] or
                type(meta.get('simulation_time_s')) not in (int, float) or
                not math.isfinite(meta['simulation_time_s']) or
                abs(meta['simulation_time_s'] - frame['time_s']) > .001):
            raise ValueError('original graph frame/time join differs')
        egos = [node for node in graph.get('nodes', []) if node.get('id') == 'ego']
        if len(egos) != 1 or type(egos[0].get('attributes', {}).get('actor_id')) is not int:
            raise ValueError('original graph ego identity missing')
        current = egos[0]['attributes']['actor_id']
        if ego_id is None:
            ego_id = current
        elif ego_id != current:
            raise ValueError('original graph ego identity changed')
    if not diagnostic:
        map_packet = json.loads((root / manifest['map']['path']).read_text())
        highway = map_packet.get('highway_sources', {})
        if set(highway) != {str(map_packet['approach_road_id']),
                            str(map_packet['destination_road_id'])}:
            raise ValueError('reviewed highway source binding missing')
    return {
        'case_id': case_id,
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'decoded_frames': saved['pixel_decode']['decoded_frames'],
        'physical_status': physical['status'],
        'diagnostic_fixture': diagnostic,
        'delivery_accepted': not diagnostic,
        'statutory_judgment': None,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--allow-diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.attempt, args.case, allow_diagnostic=args.allow_diagnostic)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
