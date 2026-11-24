"""Build four unselected 30-second exact-case constructions from prior primaries.

The selected manifest and its receipts remain untouched until the complete 30-second
saved-processing chain is regenerated. This is a CPU migration proof, not capture.
"""
from __future__ import annotations
import copy
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(value):
    if isinstance(value, dict):
        return {key: change(item) for key, item in value.items()}
    if isinstance(value, list):
        return [change(item) for item in value]
    if isinstance(value, str):
        return re.sub(r'(?<![0-9])480(?![0-9])', '600',
                      re.sub(r'(?<![0-9])24(?![0-9])', '30', value))
    if type(value) in (int, float) and value in (24, 480):
        return 30 if value == 24 else 600
    return value


def build(case):
    SOURCE = HERE / 'selected-candidates' / case / 'primary/construction.json'
    OUT = HERE / 'long-capture-matrix' / case
    source = json.loads(SOURCE.read_text())
    construction = change(source)
    # Verify the transform is limited to the clock and duration contract.
    assert construction['case_id'] == source['case_id']
    assert construction['cell_id'] == source['cell_id']
    assert construction['law_id'] == source['law_id']
    assert construction['actor'] == source['actor']
    files = {item['path']: item['content'] for item in construction['files']}
    config = json.loads(files['config.json'])
    assert config['rate_hz'] == 20 and config['duration_s'] == 30
    assert config['knobs']['duration_s'] == 30
    assert len(config['cameras']) == 4
    assert 'frames!=600' in files['runner.py']
    assert 'count!=600' in files['finalize.py']
    assert 'FRAMES=600' in files['measure.py']
    assert all('30 s / 600-frame' in row['time_window'] for row in config['recording_description']['channels'])
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / 'construction.json'
    target.write_text(json.dumps(construction, indent=2) + '\n')
    manifest = copy.deepcopy(json.loads((HERE / 'execution-manifest.json').read_text()))
    entry = next(item for item in manifest['cases'] if item['case_id'] == construction['case_id'])
    entry['construction'] = str(target.relative_to(HERE))
    entry['construction_sha256'] = sha(target)
    entry['candidates'] = []
    manifest['cases'] = [entry]
    manifest['status'] = 'unselected_30_second_cpu_migration_prototype'
    mpath = HERE / f'long-capture-matrix-{case}-manifest.json'
    generator = json.loads((HERE / f'diagnostic-{case}.json').read_text())
    for filename in ('native_samples.jsonl', 'body_history.jsonl', 'video_frames.jsonl',
                     'trace.jsonl', 'capture/evidence.jsonl', 'capture/native/frames.jsonl'):
        rows = [json.loads(line) for line in generator['files'][filename].splitlines()]
        assert len(rows) == 480
        last = rows[-1]
        for index in range(480, 600):
            row = copy.deepcopy(last)
            frame = index + 100
            time_s = (index + 1) / 20
            for key in ('frame', 'native_frame', 'carla_frame', 'original_frame', 'replay_frame'):
                if key in row:
                    row[key] = frame
            for key in ('time_s', 'recording_time_s', 'replay_simulation_time_s', 'simulation_time'):
                if key in row:
                    row[key] = time_s
            if 'video_frame' in row:
                row['video_frame'] = index
            if filename == 'capture/native/frames.jsonl':
                for key in ('base', 'abstract', 'syntax'):
                    if key in row:
                        row[key] = re.sub(r'\d{8}(?=\.pkl$)', f'{frame:08d}', row[key])
            rows.append(row)
        generator['files'][filename] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    capture_manifest = json.loads(generator['files']['capture/manifest.json'])
    capture_manifest['frames'] = 600
    capture_manifest['sources']['trace.jsonl'] = hashlib.sha256(
        generator['files']['trace.jsonl'].encode()).hexdigest()
    generator['files']['capture/manifest.json'] = json.dumps(capture_manifest, separators=(',', ':')) + '\n'
    assert len(generator['graphs']) == 480
    last_graph = generator['graphs'][-1]
    for index in range(480, 600):
        graph = copy.deepcopy(last_graph)
        frame = index + 100
        graph['path'] = re.sub(r'\d{8}(?=\.pkl$)', f'{frame:08d}', graph['path'])
        graph['attributes']['frame'] = frame
        graph['attributes']['simulation_time_s'] = (index + 1) / 20
        generator['graphs'].append(graph)
    for video in generator['videos']:
        video['frames'] = 600
    for graph in generator['graphs']:
        graph['path'] = graph['path'].removesuffix('.pkl') + '.adapter.json'
    graph_by_frame = {graph['attributes']['frame']: graph for graph in generator['graphs']}
    frame_rows = [json.loads(line) for line in generator['files']['capture/native/frames.jsonl'].splitlines()]
    generator['files']['capture/native/frames.jsonl'] = ''.join(
        json.dumps({'frame': row['frame'], 'simulation_time': row['simulation_time'],
                    'adapter_graph': graph_by_frame[row['frame']]['path'].removeprefix('capture/native/'),
                    'base': graph_by_frame[row['frame']]['path'].removeprefix('capture/native/'),
                    'nodes': len(graph_by_frame[row['frame']]['nodes']),
                    'edges': len(graph_by_frame[row['frame']]['edges'])}, separators=(',', ':')) + '\n'
        for row in frame_rows)
    gpath = OUT / 'diagnostic-generator.json'
    gpath.write_text(json.dumps(generator, separators=(',', ':')) + '\n')
    assert gpath.stat().st_size <= 2 * 1024 * 1024
    source_path = OUT / f'{case}-600.json'
    measure_path = HERE.parents[1] / '.runtime-work/c111256-long-capture-measure.py'
    measure_path.parent.mkdir(exist_ok=True)
    measure_path.write_text(files['measure.py'])
    subprocess.run([str(HERE.parents[1] / '.venv-cpu/bin/python'),
                    str(measure_path),
                    '--output', str(OUT)], check=True, capture_output=True, text=True)
    generated = source_path
    assert generated.is_file()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json',
                           'source': str(generated.relative_to(HERE.parents[1])),
                           'sha256': sha(generated)}],
              'generator': {'source': str(gpath.relative_to(HERE.parents[1])),
                            'sha256': sha(gpath)}}
    recipe_path = OUT / 'diagnostic-recipe.json'
    recipe_path.write_text(json.dumps(recipe, separators=(',', ':')) + '\n')
    entry['fixture_recipe'] = str(recipe_path.relative_to(HERE.parents[1]))
    mpath.write_text(json.dumps(manifest, indent=2) + '\n')
    receipt = {'format': 'c111256-long-capture-prototype-v1',
               'case_id': construction['case_id'],
               'selected_source_construction_sha256': sha(SOURCE),
               'prototype_construction_sha256': sha(target),
               'prototype_manifest_sha256': sha(mpath),
               'diagnostic_recipe_sha256': sha(recipe_path),
               'rate_hz': 20, 'duration_s': 30, 'frames': 600,
               'camera_names': [camera['name'] for camera in config['cameras']],
               'status': 'unselected_cpu_migration_prototype',
               'original_native_observed': False,
               'remaining': 'Regenerate selected full matrix, four-camera saved processing and source-bound audits before selection'}
    (OUT / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


def main():
    print(json.dumps([build(case) for case in CASES]))


if __name__ == '__main__':
    main()
