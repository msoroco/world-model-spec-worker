"""Build source-hashed, synthetic-only public fixtures for C111334 cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ROOT = FOLDER.parents[1]
TAXI = ROOT / 'work/training__C150173__LVMC-11-52-030-B__taxi_driver/native/diagnostic/probe_a/fixture-spec.json'
CASE_ROOT = 'training__C111334__NRS-484B-307-4b__pedestrian'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def jsonl(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(v, separators=(',', ':'), allow_nan=False) + '\n'
                            for v in values))


def body(y):
    return [[-.2, y-.2, 0], [-.2, y-.2, 1.8],
            [-.2, y+.2, 0], [-.2, y+.2, 1.8],
            [.2, y-.2, 0], [.2, y-.2, 1.8],
            [.2, y+.2, 0], [.2, y+.2, 1.8]]


def destination(suffix):
    if suffix not in ('probe_1', 'probe_2', 'permission_before_entry'):
        raise ValueError('Unknown C111334 suffix')
    return FOLDER / 'native/diagnostic' / suffix


def build(suffix='probe_2'):
    scratch = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if ROOT / '.runtime-work' not in scratch.parents:
        raise ValueError('Diagnostic generation must use .runtime-work')
    template = json.loads(TAXI.read_text())
    spec = {'files': {
        'capture/native/frames.jsonl': template['files']['capture/native/frames.jsonl'],
        'capture/recorder_info.txt': 'Synthetic C111334 walker diagnostic; no Native recording.\nCreate 101: walker.pedestrian.0001 (0)\n'},
        'graphs': [],
        'videos': [{'path': name + '.mkv', 'frames': 600, 'width': width,
                    'height': height, 'fps': 20, 'color': 'black'}
                   for name, (width, height) in zip(VIEWS, SIZES)]}
    traces, evidence, native, mapping = [], [], [], []
    rgb = {name: hashlib.sha256(bytes(width * height * 3)).hexdigest()
           for name, (width, height) in zip(VIEWS, SIZES)}
    for i in range(600):
        frame = 1000 + i
        t = (i + 1) / 20
        y = 4.0 if suffix == 'probe_1' or i < 120 else 4.0 - (i - 119) * .05
        b = body(y)
        graph = template['graphs'][i]
        graph['nodes'] = [{'id': 'ego', 'attributes': {
            'entity_id': 101, 'sem_class': 'ego', 'vertex': [0, y, .9],
            'forward': [0, -1, 0], 'threedbbox': b}}]
        spec['graphs'].append(graph)
        traces.append({'frame': frame, 'time_s': t, 'pedestrian_actor_id': 101,
            'position_m': [0, y, .9], 'position': {'x': 0, 'y': y, 'z': .9},
            'heading_deg': -90, 'speed_mps': 0 if i < 120 else 1,
            'speed_mph': 0 if i < 120 else 1 / .44704,
            'velocity_mps': [0, 0 if i < 120 else -1, 0],
            'control': {},
            'source_kind': 'synthetic_cpu_fixture'})
        evidence.append({'actor_id': 101, 'original_frame': frame,
            'replay_frame': frame, 'recording_time_s': t,
            'replay_simulation_time_s': t,
            'ego': {'position_m': [0, y, .9], 'body_vertices_m': b,
                    'heading_deg': -90, 'speed_mps': 0 if i < 120 else 1,
                    'speed_provenance': 'synthetic_native_sample',
                    'synthetic_diagnostic': True},
            'other_actors': [], 'world': {'road_projection': {
                'road_id': 1, 'lane_id': -1, 'section_id': 0, 's_m': 15}}})
        native.append({'video_frame': i, 'native_frame': frame,
            'time_s': t, 'pedestrian_id': 101,
            'pedestrian_xy_m': [0, y],
            'pedestrian_body_polygon_xy_m': [[-.2, y-.2], [.2, y-.2],
                                              [.2, y+.2], [-.2, y+.2]],
            'arrow_head_id': 'C111334-facing-green-turn-arrow',
            'other_device_id': 'C111334-other-permitting-device',
            'synthetic_diagnostic': True})
        mapping.append({'video_frame': i, 'carla_frame': frame,
            'native_frame': frame, 'time_s': t,
            'camera_native_frames': {name: frame for name in VIEWS},
            'source_rgb_sha256': rgb})
    dest = destination(suffix)
    dest.mkdir(parents=True, exist_ok=True)
    sources = dest / 'sources'
    dump(dest / 'fixture-spec.json', spec)
    jsonl(sources / 'capture/evidence.jsonl', evidence)
    jsonl(sources / 'trace.jsonl', traces)
    jsonl(sources / 'video_frames.jsonl', mapping)
    jsonl(sources / 'c111334-native-samples.jsonl', native)
    (sources / 'road.xodr').write_text((HERE / 'road.xodr').read_text())
    dump(sources / 'capture/manifest.json', {'extraction_confirmed': True,
        'frames': 600, 'synthetic_diagnostic': True,
        'sources': {name: sha(sources / name) for name in
            ('road.xodr', 'trace.jsonl', 'c111334-native-samples.jsonl')}})
    return dest, spec


def bind_review(videos, suffix='probe_2'):
    dest = destination(suffix)
    sources = dest / 'sources'
    bound = {name: sha(sources / name) for name in
             ('c111334-native-samples.jsonl', 'video_frames.jsonl')}
    bound.update({name + '.mkv': sha(videos / (name + '.mkv')) for name in VIEWS})
    review = {'format': 'c111334-device-review-v1', 'case_id': CASE_ROOT + '__' + suffix,
        'reviewer': 'synthetic CPU diagnostic',
        'review_method': 'source-shaped positive/negative processing test',
        'source_kind': 'synthetic_cpu_fixture', 'original_pixels_reviewed': False,
        'source_sha256': bound, 'green_turn_arrow_alone_by_frame': [True]*600,
        'arrow_faces_pedestrian_by_frame': [True]*600,
        'other_device_permits_proceed_by_frame': [suffix == 'permission_before_entry' and i >= 100
                                                   for i in range(600)],
        'other_device_governs_pedestrian_by_frame': [True]*600}
    dump(sources / 'device-review.json', review)
    paths = sorted(p for p in sources.rglob('*') if p.is_file()
                   and p.relative_to(sources).as_posix() != 'road.xodr')
    recipe = {'format': 'worker-fixture-recipe',
        'generator': {'source': str((dest / 'fixture-spec.json').relative_to(ROOT)),
                      'sha256': sha(dest / 'fixture-spec.json')},
        'sources': [{'path': str(p.relative_to(sources)),
                     'source': str(p.relative_to(ROOT)), 'sha256': sha(p)}
                    for p in paths]}
    dump(dest / 'fixture-recipe.json', recipe)
    return {'fixture_spec_sha256': sha(dest / 'fixture-spec.json'),
            'fixture_recipe_sha256': sha(dest / 'fixture-recipe.json'),
            'sources': len(paths)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', default='probe_2',
                        choices=('probe_1', 'probe_2', 'permission_before_entry'))
    args = parser.parse_args()
    target, specification = build(args.suffix)
    print(json.dumps({'fixture_spec': str(target / 'fixture-spec.json'),
                      'graphs': len(specification['graphs'])}))
