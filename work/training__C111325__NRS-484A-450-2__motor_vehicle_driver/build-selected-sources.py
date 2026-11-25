"""Extend retained synthetic source fixtures for current measured-speed rendering."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def build():
    results = []
    for index in (1, 2):
        old = HERE / f'current-v2-probe-{index}-fixture'
        selected = HERE / f'selected-source-probe-{index}'
        selected.mkdir(exist_ok=True)
        for source in sorted(old.rglob('*')):
            if source.is_file():
                destination = selected / source.relative_to(old)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, destination)
        trace = [json.loads(line) for line in (selected / 'trace.jsonl').read_text().splitlines()]
        native = [json.loads(line) for line in (selected / 'native_samples.jsonl').read_text().splitlines()]
        if len(trace) != 600 or len(native) != 600:
            raise ValueError('Full source window missing')
        for t, n in zip(trace, native):
            if t['frame'] != n['native_frame'] or t['time_s'] != n['time_s']:
                raise ValueError('Source frame/time join differs')
            t['velocity_mps'] = [0.0, n['speed_mps'], 0.0]
        (selected / 'trace.jsonl').write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                                    for row in trace))
        capture = selected / 'capture/manifest.json'
        capture_data = json.loads(capture.read_text())
        capture_data['sources']['trace.jsonl'] = sha(selected / 'trace.jsonl')
        write(capture, capture_data)
        (selected / 'stop_history.jsonl').write_text(''.join(json.dumps({
            'frame': row['native_frame'], 'time_s': row['time_s'],
            'body_vertices_m': row['body_vertices_m']}, allow_nan=False) + '\n'
            for row in native))
        write(selected / 'crosswalk_geometry.json', {
            'intersection_polygon_xy_m': [[-7, -7], [7, -7], [7, 7], [-7, 7]],
            'crosswalk_near_edge_y_m': -11,
            'road_sha256': sha(selected / 'road.xodr'),
            'source': 'authored OpenDRIVE junction extent; physical review pending',
        })
        spec = HERE / f'current-v2-probe-{index}-fixture-spec.json'
        recipe = HERE / f'selected-probe-{index}-fixture-recipe.json'
        write(recipe, {'format': 'worker-fixture-recipe',
                       'sources': [{'path': p.relative_to(selected).as_posix(),
                                    'source': p.relative_to(ROOT).as_posix(), 'sha256': sha(p)}
                                   for p in sorted(selected.rglob('*')) if p.is_file()],
                       'generator': {'source': spec.relative_to(ROOT).as_posix(),
                                     'sha256': sha(spec)}})
        results.append({'case': index, 'recipe_sha256': sha(recipe),
                        'trace_sha256': sha(selected / 'trace.jsonl')})
    draft = HERE / 'selected-draft-execution-manifest.json'
    manifest = json.loads(draft.read_text())
    for index, entry in enumerate(manifest['cases'], start=1):
        entry['fixture_recipe'] = f'work/{HERE.name}/selected-probe-{index}-fixture-recipe.json'
    write(draft, manifest)
    return results


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
