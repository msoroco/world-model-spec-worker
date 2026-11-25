"""Build source-hashed sight-point CPU fixtures with explicit proxy provenance."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, body):
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + '\n')


def build():
    reports = []
    for label in ('stop', 'pass'):
        source = HERE / f'selected-source-line_{label}'
        target = HERE / f'selected-source-sight_{label}'
        target.mkdir(exist_ok=True)
        for path in sorted(source.rglob('*')):
            if path.is_file():
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
        shutil.copyfile(HERE / 'native/road_sight_point.xodr', target / 'road.xodr')
        samples = [json.loads(line) for line in (target / 'native_samples.jsonl').read_text().splitlines()]
        sight = []
        for sample in samples:
            center_y = sum(vertex[1] for vertex in sample['body_vertices_m']) / 8
            frame = sample['video_frame']
            actor_x = -20 + 0.02 * frame
            def at_x(x):
                return center_y + (x - 1.75) / (actor_x - 1.75) * (0 - center_y)
            low, high = sorted((at_x(-0.5), at_x(0)))
            sight.append({'native_frame': sample['native_frame'], 'time_s': sample['time_s'],
                          'approaching_traffic': True,
                          'view_open': not (high >= -40 and low <= -13),
                          'view_source_kind': 'synthetic_view_proxy',
                          'intersecting_actor_approach': 'west_to_east',
                          'intersecting_actor_xy_m': [actor_x, 0],
                          'observer_eye_xy_m': [1.75, center_y],
                          'occluder_xy_bounds_m': [-0.5, 0, -40, -13]})
        (target / 'sight_samples.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in sight))
        case_id = HERE.name + '__sight_' + label
        identity = json.loads((target / 'diagnostic-source-manifest.json').read_text())
        identity['case_id'] = case_id
        identity['sha256']['road.xodr'] = sha(target / 'road.xodr')
        identity['sha256']['sight_samples.jsonl'] = sha(target / 'sight_samples.jsonl')
        identity['sha256']['video_frames.jsonl'] = sha(target / 'video_frames.jsonl')
        write(target / 'diagnostic-source-manifest.json', identity)
        capture = json.loads((target / 'capture/manifest.json').read_text())
        capture['sources']['road.xodr'] = sha(target / 'road.xodr')
        capture['sources']['sight_samples.jsonl'] = sha(target / 'sight_samples.jsonl')
        write(target / 'capture/manifest.json', capture)
        geometry = json.loads((target / 'crosswalk_geometry.json').read_text())
        geometry.pop('marked_stop_line_y_m', None)
        geometry['sight_point_proxy_y_m'] = -11
        geometry['road_sha256'] = sha(target / 'road.xodr')
        geometry['source'] = 'authored no-reference road plus synthetic view proxy; physical visibility unverified'
        write(target / 'crosswalk_geometry.json', geometry)
        index = 1 if label == 'stop' else 2
        spec = HERE / f'current-v2-probe-{index}-fixture-spec.json'
        recipe = HERE / f'selected-sight_{label}-fixture-recipe.json'
        write(recipe, {'format': 'worker-fixture-recipe',
                       'sources': [{'path': p.relative_to(target).as_posix(),
                                    'source': p.relative_to(ROOT).as_posix(),
                                    'sha256': sha(p)}
                                   for p in sorted(target.rglob('*')) if p.is_file()],
                       'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                     'sha256': sha(spec)}})
        contract = json.loads((HERE / f'selected-line_{label}-measurement-contract.json').read_text())
        contract['case_id'] = case_id
        requirement = contract['requirements'][0]
        requirement['disposition_index'] = 2
        requirement['output_key'] = 'sight_point_stop'
        requirement['method'] = 'measure_sight_point'
        requirement['inputs'] = ['native_samples.jsonl', 'road.xodr',
                                 'sight_samples.jsonl', 'video_frames.jsonl']
        write(HERE / f'selected-sight_{label}-measurement-contract.json', contract)
        reports.append({'case_id': case_id, 'recipe_sha256': sha(recipe),
                        'sight_sha256': sha(target / 'sight_samples.jsonl')})
    return reports


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
