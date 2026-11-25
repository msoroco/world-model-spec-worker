"""Extend the stationary tail of a synthetic rider source to 600 frames.

The extension is a CPU compatibility input, never an original Native claim.
The first 480 diagnostic frames and their measurements are preserved.
"""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = HERE / 'rider-v2-bicycle-clear-primary/source'
NEW = HERE / 'rider-30s-primary/source'
SPEC = HERE / 'rider-30s-primary/diagnostic-spec.json'
RECIPE = HERE / 'rider-30s-primary/fixture-recipe.json'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ROW_FILES = ('trace.jsonl', 'video_frames.jsonl', 'rider_native_samples.jsonl',
             'native_samples.jsonl', 'body_history.jsonl',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def extend(row, index):
    value = copy.deepcopy(row)
    frame = 100 + index
    time = round((index + 1) / 20, 6)
    for key in ('frame', 'native_frame', 'carla_frame', 'original_frame', 'replay_frame'):
        if key in value:
            value[key] = frame
    for key in ('time_s', 'recording_time_s', 'replay_simulation_time_s', 'simulation_time'):
        if key in value:
            value[key] = time
    if 'video_frame' in value:
        value['video_frame'] = index
    if 'original_observations' in value:
        value['original_observations']['frame'] = frame
        value['original_observations']['time_s'] = time
        for camera in CAMERAS:
            value['original_observations']['rgb_sensors'][camera]['frame'] = frame
    if 'adapter_graph' in value:
        value['adapter_graph'] = f'graphs/base/{frame:08d}.adapter.json'
        value['base'] = value['adapter_graph']
        value['abstract'] = f'graphs/abstract/{frame:08d}.pkl'
    return value


def main():
    shutil.copytree(OLD, NEW, dirs_exist_ok=True)
    for relative in ROW_FILES:
        path = NEW / relative
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 480
        rows.extend(extend(rows[-1], index) for index in range(480, 600))
        if relative == 'trace.jsonl':
            for row in rows:
                heading = math.radians(row['heading_deg'])
                speed = row['speed_mps']
                row['velocity_mps'] = [speed * math.cos(heading), speed * math.sin(heading), 0.0]
        write_rows(path, rows)
    graph_dir = NEW / 'capture/native/graphs/base'
    final_graph = json.loads((graph_dir / '00000579.adapter.json').read_text())
    for index in range(480, 600):
        frame = index + 100
        time = round((index + 1) / 20, 6)
        graph = copy.deepcopy(final_graph)
        graph['metadata']['frame'] = frame
        graph['metadata']['simulation_time_s'] = time
        observation = graph['metadata']['observed_evidence']
        observation['frame'] = frame
        observation['time_s'] = time
        for camera in CAMERAS:
            observation['rgb_sensors'][camera]['frame'] = frame
        (graph_dir / f'{frame:08d}.adapter.json').write_text(
            json.dumps(graph, separators=(',', ':')) + '\n')
    capture_manifest = json.loads((NEW / 'capture/manifest.json').read_text())
    capture_manifest['frames'] = 600
    capture_manifest['sources']['trace.jsonl'] = sha(NEW / 'trace.jsonl')
    write(NEW / 'capture/manifest.json', capture_manifest)
    rider_manifest = json.loads((NEW / 'rider-source-manifest.json').read_text())
    rider_manifest['samples_sha256'] = sha(NEW / 'rider_native_samples.jsonl')
    write(NEW / 'rider-source-manifest.json', rider_manifest)
    entry = json.loads((NEW / 'entry-sources.json').read_text())
    entry['sha256']['native_samples.jsonl'] = sha(NEW / 'native_samples.jsonl')
    write(NEW / 'entry-sources.json', entry)
    spec = json.loads((HERE / 'rider-v2-bicycle-clear-primary/diagnostic-spec.json').read_text())
    for video in spec['videos']:
        video['frames'] = 600
        if video['path'] != 'overview.mkv':
            video['width'] = 1280
            video['height'] = 720
    write(SPEC, spec)
    sources = []
    for path in sorted(NEW.rglob('*')):
        if path.is_file():
            sources.append({'path': str(path.relative_to(NEW)),
                            'source': str(path.relative_to(ROOT)),
                            'sha256': sha(path)})
    write(RECIPE, {'format': 'worker-fixture-recipe',
                   'generator': {'source': str(SPEC.relative_to(ROOT)),
                                 'sha256': sha(SPEC)},
                   'sources': sources})
    print(json.dumps({'frames': 600, 'duration_s': 30,
                      'source_count': len(sources),
                      'recipe_sha256': sha(RECIPE),
                      'scope': 'synthetic source extension only'}))


if __name__ == '__main__':
    main()
