"""Extend the retained synthetic source probe to the 30-second Native contract.

The 12-second crossing and phase-change portion is unchanged. Added frames hold
the walker at the far-side safe location under a steady signal. This is only a
software fixture and does not supply original signal pixels or governance.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE_FRAMES = 240
TOTAL_FRAMES = 600
FIRST_FRAME = 100


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def dump_rows(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def build(suffix):
    source_path = HERE / ('diagnostic-' + suffix + '.json')
    source = json.loads(source_path.read_text())
    assert len(source['graphs']) == SOURCE_FRAMES
    files = source['files']
    names = ('capture/evidence.jsonl', 'capture/native/frames.jsonl',
             'no-countdown-samples.jsonl', 'trace.jsonl', 'video_frames.jsonl')
    rows = {name: read_rows(files[name]) for name in names}
    assert all(len(values) == SOURCE_FRAMES for values in rows.values())
    for graph in source['graphs']:
        graph['path'] = graph['path'].removesuffix('.pkl') + '.adapter.json'
    for row in rows['capture/native/frames.jsonl']:
        row['adapter_graph'] = row.pop('base').removesuffix('.pkl') + '.adapter.json'
        row.pop('abstract', None)
    for index in range(SOURCE_FRAMES, TOTAL_FRAMES):
        frame = FIRST_FRAME + index
        time_s = round(index / 20, 6)
        evidence = copy.deepcopy(rows['capture/evidence.jsonl'][-1])
        evidence.update(original_frame=frame, replay_frame=frame,
                        recording_time_s=time_s, replay_simulation_time_s=time_s)
        evidence['ego']['speed_mps'] = 0.0
        rows['capture/evidence.jsonl'].append(evidence)
        native = copy.deepcopy(rows['capture/native/frames.jsonl'][-1])
        native.update(frame=frame, time_s=time_s, simulation_time=time_s,
                      adapter_graph=f'graphs/base/{frame:08d}.adapter.json')
        rows['capture/native/frames.jsonl'].append(native)
        sample = copy.deepcopy(rows['no-countdown-samples.jsonl'][-1])
        sample.update(native_frame=frame, time_s=time_s)
        rows['no-countdown-samples.jsonl'].append(sample)
        trace = copy.deepcopy(rows['trace.jsonl'][-1])
        trace.update(frame=frame, time_s=time_s, speed_mps=0.0, speed_mph=0.0)
        rows['trace.jsonl'].append(trace)
        mapping = copy.deepcopy(rows['video_frames.jsonl'][-1])
        mapping.update(video_frame=index, native_frame=frame,
                       carla_frame=frame, time_s=time_s)
        rows['video_frames.jsonl'].append(mapping)
        graph = copy.deepcopy(source['graphs'][-1])
        graph['path'] = 'capture/native/graphs/base/' + f'{frame:08d}.adapter.json'
        graph['attributes'].update(frame=frame, simulation_time_s=time_s)
        source['graphs'].append(graph)
    for name, values in rows.items():
        files[name] = dump_rows(values)
    capture = json.loads(files['capture/manifest.json'])
    capture['frames'] = TOTAL_FRAMES
    capture['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(capture) + '\n'
    for video in source['videos']:
        video['frames'] = TOTAL_FRAMES
    spec_path = HERE / ('diagnostic30-' + suffix + '.json')
    spec_path.write_text(json.dumps(source, separators=(',', ':')) + '\n')
    if spec_path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('30-second source generator exceeds return limit')
    relative = spec_path.relative_to(ROOT).as_posix()
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                           'sha256': sha(spec_path)}],
              'generator': {'source': relative, 'sha256': sha(spec_path)}}
    recipe_path = HERE / ('diagnostic30-' + suffix + '-recipe.json')
    recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
    return {'suffix': suffix, 'frames': TOTAL_FRAMES, 'spec_bytes': spec_path.stat().st_size,
            'spec_sha256': sha(spec_path), 'recipe_sha256': sha(recipe_path)}


def main():
    records = [build(suffix) for suffix in ('controlled_1', 'controlled_2')]
    manifest_path = HERE / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for suffix, entry in zip(('controlled_1', 'controlled_2'), manifest['cases']):
        assert entry['case_id'].endswith(suffix)
        entry['fixture_recipe'] = 'work/' + HERE.name + '/diagnostic30-' + suffix + '-recipe.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'records': records, 'manifest_sha256': sha(manifest_path)}, sort_keys=True))


if __name__ == '__main__':
    main()
