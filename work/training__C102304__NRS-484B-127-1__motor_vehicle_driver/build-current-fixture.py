"""Build a source-inventoried 45-second diagnostic for the current adapter.

All rows are synthetic software probes. This never reconstructs Native pixels.
"""
import hashlib
import json
import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--condition', choices=('condition_a', 'condition_b'), default='condition_a')
    condition = parser.parse_args().condition
    summary = json.loads((HERE / 'saved-following-summary.json').read_text())
    record = next(row for row in summary['records'] if row['case_suffix'] == condition)
    retained = Path(record['retained_positive'])
    if not retained.is_dir():
        raise ValueError('Retained original-source fixture unavailable; regenerate saved proof')
    source_dir = HERE / 'current-fixture' / condition
    source_dir.mkdir(parents=True, exist_ok=True)
    source_names = ['native_samples.jsonl', 'following_context.json', 'trace.jsonl',
                    'capture/evidence.jsonl', 'capture/manifest.json',
                    'capture/recorder_info.txt', 'road.xodr', 'video_frames.jsonl']
    for name in source_names:
        target = source_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((retained / name).read_bytes())
    samples = [json.loads(row) for row in (source_dir / 'native_samples.jsonl').read_text().splitlines()]
    if len(samples) != 900:
        raise ValueError('Diagnostic must retain the full 45-second interval')
    native_rows = []
    graphs = []
    for item in samples:
        frame = item['native_frame']
        relative = f'graphs/base/{frame:08d}.adapter.json'
        native_rows.append({'frame': frame, 'time_s': item['time_s'],
                            'simulation_time': item['time_s'], 'adapter_graph': relative,
                            'synthetic_diagnostic': True})
        body = item['ego']['native_body_xy_m']
        x = sum(p[0] for p in body) / len(body)
        y = sum(p[1] for p in body) / len(body)
        graphs.append({'path': 'capture/native/' + relative,
                       'attributes': {'frame': frame, 'time_s': item['time_s']},
                       'nodes': [{'id': 'ego', 'attributes': {
                           'vertex': [x, y, 0.5], 'sem_class': 'ego',
                           'forward': [1.0, 0.0, 0.0], 'entity_id': 107,
                           'carla_speed': item['ego']['speed_mps'],
                           'special_class': 'ego'}}], 'edges': []})
    frames_path = source_dir / 'capture/native/frames.jsonl'
    frames_path.parent.mkdir(parents=True, exist_ok=True)
    frames_path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                   for row in native_rows))
    source_names.append('capture/native/frames.jsonl')
    cameras = [('overview', 1920, 1080), ('approach', 1280, 720),
               ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]
    specification = {'files': {}, 'graphs': graphs,
                     'videos': [{'path': name+'.mkv', 'frames': 900,
                                 'width': width, 'height': height, 'fps': 20,
                                 'color': 'black'} for name, width, height in cameras]}
    spec_path = HERE / 'current-fixture' / (condition + '-generator.json')
    spec_path.write_text(json.dumps(specification, separators=(',', ':')) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Generator specification exceeds returned-file limit')
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': name,
                           'source': (source_dir / name).relative_to(ROOT).as_posix(),
                           'sha256': sha(source_dir / name)} for name in source_names],
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec_path)}}
    recipe_path = HERE / 'current-fixture' / (condition + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'condition': condition, 'frames': len(samples), 'sources': len(source_names),
                      'graphs': len(graphs), 'generator_bytes': spec_path.stat().st_size,
                      'recipe_sha256': sha(recipe_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
