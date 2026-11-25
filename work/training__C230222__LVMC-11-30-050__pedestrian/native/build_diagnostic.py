"""Build a source-shaped 600-frame crossing diagnostic from a same-cell schema.

The source skeleton is synthetic; all positions and route observations are
re-authored for this law. No original recording or physical verdict is claimed.
"""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
SKELETON = REPO / 'work/training__C230222__NRS-484B-283-1b__pedestrian/v2-primary/probe_1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def write_lines(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in data))


def pose(frame, condition):
    fraction = min(1.0, frame / 300)
    return [-3.5 + 7 * fraction, 0.0 if condition == 'right_angle' else 2.8 * fraction, .5]


def main():
    skeleton = SKELETON / 'sources'
    base_generator = json.loads((SKELETON / 'generator.json').read_text())
    for suffix, condition in (('a', 'right_angle'), ('b', 'longer_diagonal')):
        case = ROOT / 'diagnostic' / ('condition_' + suffix)
        source = case / 'sources'
        source.mkdir(parents=True, exist_ok=True)
        trace = lines(skeleton / 'trace.jsonl')
        evidence = lines(skeleton / 'capture/evidence.jsonl')
        native = lines(skeleton / 'capture/native/frames.jsonl')
        mapping = lines(skeleton / 'video_frames.jsonl')
        graphs = copy.deepcopy(base_generator['graphs'])
        samples = []
        frame_hashes = {name: hashlib.sha256(bytes((1920 * 1080 if name == 'overview' else 1280 * 720) * 3)).hexdigest()
                        for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}
        for index, (t, e, n, m, graph) in enumerate(zip(trace, evidence, native, mapping, graphs)):
            p = pose(index, condition)
            speed = 0 if index >= 300 else math.hypot(7, 0 if condition == 'right_angle' else 2.8) / 15
            t['position'] = {'x': p[0], 'y': p[1], 'z': p[2]}
            t['position_m'], t['speed_mps'] = p, speed
            t['speed_mph'] = speed / .44704
            t['velocity_mps'] = [speed * (7 / math.hypot(7, 0 if condition == 'right_angle' else 2.8)),
                                 0 if condition == 'right_angle' else speed * 2.8 / math.hypot(7, 2.8), 0]
            t['heading_deg'] = 0 if condition == 'right_angle' else math.degrees(math.atan2(2.8, 7))
            e['ego']['position_m'], e['ego']['speed_mps'] = p, speed
            e['ego']['heading_deg'] = t['heading_deg']
            e['ego']['body_vertices_m'] = [[p[0] + dx, p[1] + dy, z]
                for dx, dy, z in ((-.12,-.12,0),(-.12,-.12,1.8),(.12,-.12,0),
                                  (.12,-.12,1.8),(.12,.12,0),(.12,.12,1.8),
                                  (-.12,.12,0),(-.12,.12,1.8))]
            node = graph['nodes'][0]['attributes']
            node['vertex'] = p
            node['threedbbox'] = e['ego']['body_vertices_m']
            m['source_rgb_sha256'] = frame_hashes
            samples.append({'native_frame': m['native_frame'], 'time_s': m['time_s'],
                            'pedestrian_id': 17, 'pedestrian_xy_m': p[:2],
                            'pedestrian_speed_mps': speed,
                            'original_frame_sha256': frame_hashes['reference_corner'],
                            'synthetic_diagnostic': True})
        write_lines(source / 'trace.jsonl', trace)
        write_lines(source / 'capture/evidence.jsonl', evidence)
        write_lines(source / 'capture/native/frames.jsonl', native)
        write_lines(source / 'video_frames.jsonl', mapping)
        write_lines(source / 'route-samples.jsonl', samples)
        manifest = json.loads((skeleton / 'capture/manifest.json').read_text())
        manifest['sources']['trace.jsonl'] = sha(source / 'trace.jsonl')
        write(source / 'capture/manifest.json', manifest)
        (source / 'capture/recorder_info.txt').write_text((skeleton / 'capture/recorder_info.txt').read_text().rstrip() + '\n')
        context = {'source_kind': 'synthetic_cpu_fixture', 'expected_frames': 600,
                   'origin_curb_xy_m': [[-3.5,-20],[-3.5,20]],
                   'opposite_curb_xy_m': [[3.5,-20],[3.5,20]],
                   'crosswalk_polygons_xy_m': [],
                   'road_geometry_sha256': sha(HERE / 'road.xodr'),
                   'original_map_and_pixel_reviewed': False,
                   'synthetic_diagnostic': True}
        write(source / 'route-context.json', context)
        generator = {'files': {}, 'graphs': graphs,
                     'videos': [{'path': name + '.mkv', 'frames': 600,
                                'width': 1920 if name == 'overview' else 1280,
                                'height': 1080 if name == 'overview' else 720,
                                'fps': 20, 'color': 'black'}
                                for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
        write(case / 'generator.json', generator)
        inventory = ['trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl',
                     'video_frames.jsonl', 'route-samples.jsonl', 'route-context.json',
                     'capture/manifest.json', 'capture/recorder_info.txt']
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': name, 'source': str((source / name).relative_to(REPO)),
                               'sha256': sha(source / name)} for name in inventory],
                  'generator': {'source': str((case / 'generator.json').relative_to(REPO)),
                                'sha256': sha(case / 'generator.json')}}
        write(case / 'recipe.json', recipe)
        print(json.dumps({'condition': suffix, 'recipe_sha256': sha(case / 'recipe.json'),
                          'generator_sha256': sha(case / 'generator.json')}))


if __name__ == '__main__':
    main()
