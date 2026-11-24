"""Generate a coherent 900-frame synthetic Native-shaped departure audit input."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from physical_fixture import make_sources

HERE = Path(__file__).resolve().parent
CAMERAS = ('dash', 'front', 'left', 'right')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def materialize(root, case):
    root = Path(root).resolve()
    if '.runtime-work' not in root.parts or root.exists():
        raise ValueError('Use fresh .runtime-work diagnostic delivery fixture')
    make_sources(root, 'complete_motion', case)
    name = case.removeprefix(HERE.name + '__')
    if name not in ('near_centerline', 'farther_from_centerline',
                    'imaginary_near_centerline', 'imaginary_farther_from_centerline'):
        raise ValueError('wrong exact case')
    body = rows(root / 'body_history.jsonl')
    frame_map = rows(root / 'video_frames.jsonl')
    offset = 1.5 if name.endswith('near_centerline') else 3.0
    for i in range(600, 900):
        for vertex in body[i]['body_vertices_m']:
            vertex[0] += offset
    (root / 'body_history.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in body))
    trace_rows = []
    for i, row in enumerate(body):
        phase = ('approach' if i < 300 else 'intersection_entry' if i == 300
                 else 'turning' if i < 600 else 'departure')
        vertices = [point[:2] for point in row['body_vertices_m']]
        center = [sum(point[axis] for point in vertices) / len(vertices)
                  for axis in (0, 1)]
        trace_rows.append({
            'frame': row['frame'], 'elapsed_seconds': row['time_s'],
            'phase': phase, 'road_id': row['road_id'],
            'position_xy_m': center, 'body_corners_xy_m': vertices,
            'heading_rad': 0.0 if i < 300 else .7853981633974483 if i < 600 else 1.5707963267948966,
            'speed_mps': 5.0, 'driver_control': True,
        })
    trace = {'case_id': case, 'approach_road_id': 'A',
             'destination_road_id': 'B', 'maneuver': 'left_turn',
             'driver_control': True, 'samples': trace_rows}
    write(root / 'original-trace.json', trace)
    map_source = root / 'original-map.xodr'
    map_source.write_text('<OpenDRIVE><header name="diagnostic-only"/></OpenDRIVE>\n')
    map_packet = {
        'case_id': case, 'road_kind': 'two_directional_intersection',
        'approach_road_id': 'A', 'destination_road_id': 'B',
        'approach_two_directional': True, 'destination_two_directional': True,
        'approach_highway_status': 'source_verified',
        'destination_highway_status': 'source_verified',
        'centerline_kind': 'source_derived_imaginary' if name.startswith('imaginary_') else 'mapped',
        'centerline_origin_xy_m': [0, 0], 'destination_direction_xy': [0, 1],
        'centerline_source': 'synthetic test geometry',
        'direction_source': 'synthetic test geometry',
        'source_path': map_source.name, 'source_sha256': sha(map_source),
    }
    write(root / 'original-map-packet.json', map_packet)
    camera_index = {'case_id': case, 'channels': {name: [] for name in CAMERAS}}
    for channel_number, channel in enumerate(CAMERAS):
        directory = root / 'original-cameras' / channel
        directory.mkdir(parents=True)
        for i, frame in enumerate(frame_map):
            path = directory / f'{i:04d}-{frame["carla_frame"]}.png'
            image = Image.new('RGB', (16, 16),
                              ((i + channel_number) % 256, (i // 3) % 256,
                               channel_number * 35))
            image.save(path, format='PNG')
            camera_index['channels'][channel].append({
                'frame': frame['carla_frame'], 'channel': channel,
                'source_path': path.relative_to(root).as_posix(),
                'source_sha256': sha(path)})
    write(root / 'original-camera-index.json', camera_index)
    manifest = {
        'case_id': case, 'acquisition_kind': 'diagnostic_fixture',
        'rate_hz': 20, 'duration_s': 45, 'camera_media_kind': 'original_png_frames',
        'map': {'path': 'original-map-packet.json',
                'sha256': sha(root / 'original-map-packet.json')},
        'trace': {'path': 'original-trace.json',
                  'sha256': sha(root / 'original-trace.json')},
        'camera_index': {'path': 'original-camera-index.json',
                         'sha256': sha(root / 'original-camera-index.json')},
    }
    write(root / 'source-manifest.json', manifest)
    graph_rows = []
    graph_dir = root / 'graphs'
    graph_dir.mkdir()
    for frame in frame_map:
        graph = {
            'format': 'native-adapter-graph-v1',
            'metadata': {'frame': frame['carla_frame'],
                         'simulation_time_s': frame['time_s'],
                         'source': 'synthetic_cpu_fixture'},
            'nodes': [{'id': 'ego', 'attributes': {'actor_id': 1,
                       'source_actor_id': 1, 'type_id': 'vehicle.diagnostic'}}],
            'edges': [],
        }
        path = graph_dir / f'{frame["carla_frame"]:08d}.adapter.json'
        write(path, graph)
        graph_rows.append({'frame': frame['carla_frame'],
                           'adapter_graph': path.relative_to(root).as_posix(),
                           'sha256': sha(path)})
    (root / 'graph-frames.jsonl').write_text(''.join(json.dumps(row) + '\n'
                                                   for row in graph_rows))
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = materialize(args.output, args.case)
    print(json.dumps({'case_id': args.case, 'diagnostic_fixture': True,
                      'frames': 900, 'camera_pngs': 3600,
                      'path': str(result)}, sort_keys=True))


if __name__ == '__main__':
    main()
