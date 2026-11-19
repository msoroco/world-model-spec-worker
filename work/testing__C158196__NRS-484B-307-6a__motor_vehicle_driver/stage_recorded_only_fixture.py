"""Stage a synthetic acquisition-only attempt for exact recorded-only replay."""
import hashlib
import argparse
import json
import shutil
import sys
from pathlib import Path

import networkx as nx

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/python'))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from traffic_spec_adapter.adapter import write_adapter_graph
from worker_exchange.runtime_cli import materialize

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('entry_before_red', 'entry_at_red', 'entry_after_red'), default='entry_before_red')
    args = parser.parse_args()
    case = HERE.name + '__' + args.case
    stem = 'at-red' if args.case == 'entry_at_red' else 'after-red'
    root = REPO / ('.runtime-work/c158196-yellow-red-recorded-only' if args.case == 'entry_before_red' else '.runtime-work/c158196-yellow-red-' + stem + '-recorded-only')
    attempt = root / 'acquisition'
    source = REPO / ('.runtime-work/c158196-yellow-red-four-camera-validation/attempt' if args.case == 'entry_before_red' else '.runtime-work/c158196-yellow-red-' + stem + '-four-camera/attempt')
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True)
    materialize(HERE / 'execution-manifest.json', case, attempt)
    for name in ('signal_vehicle_history.jsonl', 'video_frames.jsonl', 'junction_context.json',
                 'trace.jsonl', 'acquisition-provenance.json',
                 'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'):
        shutil.copy2(source / name, attempt / name)
    trace_path = attempt / 'trace.jsonl'
    trace_rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    for row in trace_rows:
        row['speed_mph'] = row['speed_mps'] / 0.44704
        row['velocity_mps'] = [row['speed_mps'], 0.0, 0.0]
        row['control'] = {'throttle': 0.0, 'brake': 0.0,
                          'hand_brake': False, 'steer': 0.0, 'reverse': False}
    trace_path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                                  for row in trace_rows))
    shutil.copy2(HERE / 'yellow-red-site.xodr', attempt / 'road.xodr')
    capture = attempt / 'capture'
    graph_root = capture / 'native' / 'graphs'
    for kind in ('base', 'abstract'):
        (graph_root / kind).mkdir(parents=True)
    histories = [json.loads(line) for line in (attempt / 'signal_vehicle_history.jsonl').read_text().splitlines()]
    traces = trace_rows
    frame_rows = []
    with (capture / 'evidence.jsonl').open('x') as evidence:
        for row, trace in zip(histories, traces):
            frame, when = row['frame'], row['time_s']
            body = row['ego_body_vertices_xy_m']
            body3 = [[v[0], v[1], z] for v in body for z in (0.0, 1.5)]
            speed = row['ego_speed_mps']
            participant = {'actor_id': 101, 'blueprint': 'vehicle.tesla.model3',
                           'position_m': trace['position_m'], 'heading_deg': 0.0,
                           'speed_mps': speed, 'velocity_mps': [speed, 0.0, 0.0],
                           'body_vertices_m': body3, 'accel_longitudinal_mps2': 0.0}
            observations = {'frame': frame, 'time_s': when, 'participants': [],
                            'devices': [], 'relations': [],
                            'participant_inventory': 'C158196 synthetic saved-processing diagnostic',
                            'map_context': {}}
            packet = {'actor_id': 101, 'original_frame': frame,
                      'recording_time_s': when, 'replay_frame': frame,
                      'replay_simulation_time_s': when, 'supporting_only': True,
                      'original_observations': observations,
                      'ego': {'position_m': trace['position_m'], 'body_vertices_m': body3,
                              'heading_deg': 0.0, 'speed_mps': speed,
                              'speed_provenance': 'synthetic_native_sample'},
                      'world': {'road_projection': {'road_id': row['road_id'],
                                                    'lane_id': row['lane_id'],
                                                    'section_id': 0, 's_m': float(frame)}},
                      'timing': {}, 'visibility': {}}
            evidence.write(json.dumps(packet, separators=(',', ':'), allow_nan=False) + '\n')
            relative = {}
            for kind in ('base', 'abstract'):
                path = graph_root / kind / (f'{frame:08d}.adapter.json')
                graph = nx.DiGraph()
                graph.graph.update({'frame': frame, 'simulation_time_s': when,
                                    'units': {'position': 'm'},
                                    'observed_evidence': observations})
                write_adapter_graph(graph, path)
                relative[kind] = 'graphs/' + kind + '/' + path.name
            frame_rows.append({'frame': frame, 'simulation_time': when,
                               'base': relative['base'], 'abstract': relative['abstract'],
                               'adapter_graph': relative['base'],
                               'capture_seconds': 0, 'extraction_seconds': 0,
                               'nodes': 0, 'edges': 0})
    (capture / 'native' / 'frames.jsonl').write_text(''.join(
        json.dumps(item, separators=(',', ':'), allow_nan=False) + '\n' for item in frame_rows))
    (capture / 'recorder_info.txt').write_text('Version: 1\nMap: OpenDriveMap\n Create 101: vehicle.tesla.model3 (0) at (-40, 1.8, 0.3)\n')
    (capture / 'manifest.json').write_text(json.dumps({
        'acquisition': 'synthetic_diagnostic', 'case_id': case,
        'extraction_confirmed': True, 'frames': len(frame_rows),
        'map': 'Carla/Maps/OpenDriveMap', 'required_observations': [],
        'sources': {'road.xodr': sha(attempt / 'road.xodr'),
                    'trace.jsonl': sha(attempt / 'trace.jsonl')},
        'status': 'draft'}, indent=2) + '\n')
    print(json.dumps({'attempt': str(attempt.relative_to(REPO)),
                      'frames': len(frame_rows), 'graphs': 2 * len(frame_rows),
                      'provenance_kind': 'synthetic_fixture'}))


if __name__ == '__main__':
    main()
