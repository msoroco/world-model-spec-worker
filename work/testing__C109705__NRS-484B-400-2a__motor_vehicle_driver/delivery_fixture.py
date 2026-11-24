"""Generate a coherent synthetic Native-shaped source for delivery audit tests."""
import argparse
import hashlib
import io
import json
import math
import pathlib
import zipfile

from PIL import Image

from physical_fixture import make_sources
from saved_delivery import CAMERAS


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def materialize(root, case_id):
    root = pathlib.Path(root)
    if '.runtime-work' not in root.resolve().parts or root.exists():
        raise ValueError('new .runtime-work diagnostic fixture required')
    make_sources(root, 'complete_motion', case_id)
    suffix = case_id.split('__')[-1]
    far = 'farther' in suffix
    imaginary = suffix.startswith('imaginary_')
    body_path = root / 'body_history.jsonl'
    body = [json.loads(line) for line in body_path.read_text().splitlines()]
    if far:
        for row in body:
            for vertex in row['body_vertices_m']:
                vertex[1] -= 1
        _write_rows(body_path, body)
    context = {
        'law_id': 'NRS-484B-400-2a', 'cell_id': 'C109705',
        'maneuver': 'left_turn', 'control': 'centerline',
        'public_highway_source': 'diagnostic source only',
        'intersecting_roads': [
            {'road_id': 'A', 'alley': False, 'lanes': [
                {'from_xy_m': [-60, -2], 'to_xy_m': [0, -2]},
                {'from_xy_m': [0, 2], 'to_xy_m': [-60, 2]}]},
            {'road_id': 'B', 'alley': False, 'lanes': [
                {'from_xy_m': [2, 0], 'to_xy_m': [2, 60]},
                {'from_xy_m': [-2, 60], 'to_xy_m': [-2, 0]}]}],
        'approach_road_id': 'A', 'departure_road_id': 'B',
        'approach_centerline_xy_m': [[-60, 0], [0, 0]],
        'approach_half_width_m': 4.0,
        'centerline_kind': 'imaginary_equidistant' if imaginary else 'marked',
        'camera_plan': 'diagnostic four-view, 20 Hz', 'duration_s': 45,
        'controller_policy': 'diagnostic fixed route'}
    (root/'intersection-context.json').write_text(json.dumps(context, sort_keys=True) + '\n')
    history = []
    for row in body:
        phase = {'A': 'approach', 'C': 'connector', 'B': 'departure'}[row['road_id']]
        history.append({'frame': row['frame'], 'time_s': row['time_s'],
                        'road_id': row['road_id'], 'phase': phase,
                        'ego_heading_rad': {'A': 0, 'C': math.pi/4, 'B': math.pi/2}[row['road_id']],
                        'ego_body_vertices_xy_m': [vertex[:2] for vertex in row['body_vertices_m']]})
    _write_rows(root/'approach-history.jsonl', history)
    frames_path = root/'video_frames.jsonl'
    frames = [json.loads(line) for line in frames_path.read_text().splitlines()]
    for index, frame in enumerate(frames):
        frame.update(frame=frame['carla_frame'], native_frame=frame['carla_frame'],
                     camera_frames={name: frame['carla_frame'] for name in CAMERAS},
                     camera_times_s={name: frame['time_s'] for name in CAMERAS})
    _write_rows(frames_path, frames)
    (root/'road.xodr').write_text('<OpenDRIVE><header name="diagnostic-only"/></OpenDRIVE>\n')
    media = {}
    for camera_index, name in enumerate(sorted(CAMERAS)):
        path = root/(name+'.zip')
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_STORED) as archive:
            for index, frame in enumerate(frames):
                image = Image.new('RGB', (16, 16),
                                  ((index+camera_index)%256, (index//3)%256, camera_index*35))
                stream = io.BytesIO()
                image.save(stream, format='PNG')
                archive.writestr(f'{index:04d}-{frame["frame"]}.png', stream.getvalue())
        media[name] = {'kind': 'original_native', 'path': path.name, 'sha256': _sha(path)}
    graph_rows = []
    for frame in frames:
        graph = {'format': 'native-adapter-graph-v1',
                 'metadata': {'frame': frame['frame'], 'simulation_time_s': frame['time_s'],
                              'source': 'synthetic_cpu_fixture'},
                 'nodes': [{'id': 'ego', 'attributes': {'actor_id': 1,
                            'source_actor_id': 1, 'type_id': 'vehicle.diagnostic'}}],
                 'edges': []}
        path = root/'graphs'/(f'{frame["frame"]:08d}.adapter.json')
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(graph, sort_keys=True) + '\n')
        graph_rows.append({'frame': frame['frame'], 'adapter_graph': path.relative_to(root).as_posix(),
                           'sha256': _sha(path)})
    _write_rows(root/'graph-frames.jsonl', graph_rows)
    source_files = ('road.xodr', 'intersection-context.json', 'approach-history.jsonl',
                    'body_history.jsonl', 'road_geometry.json', 'video_frames.jsonl', 'graph-frames.jsonl')
    acquisition = {'case_id': case_id, 'diagnostic_fixture': True,
                   'map_binding': {'public_highway_reviewed': False}, 'media': media}
    acquisition.update({name: {'kind': 'original_native', 'sha256': _sha(root/name)}
                        for name in source_files})
    (root/'acquisition.json').write_text(json.dumps(acquisition, sort_keys=True, indent=2) + '\n')
    return root


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = materialize(args.output, args.case)
    print(json.dumps({'case_id': args.case, 'diagnostic_only': True,
                      'frames': 900, 'camera_archives': 4, 'path': str(result)}, sort_keys=True))


if __name__ == '__main__':
    main()
