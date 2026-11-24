"""Build a current-runtime diagnostic recipe from the retained prior-entry source."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pickle
import copy
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extend_to_600(fixture):
    """Keep the already clear pedestrian stationary for a full diagnostic window."""
    paths = ('exception-samples.jsonl', 'trace.jsonl', 'video_frames.jsonl',
             'capture/evidence.jsonl', 'capture/native/frames.jsonl')
    rows = {name: [json.loads(line) for line in (fixture / name).read_text().splitlines()]
            for name in paths}
    if any(len(values) != 240 for values in rows.values()):
        raise ValueError('Expected retained 240-frame source before extension')
    native_base = rows['capture/native/frames.jsonl'][-1]['base']
    last_graph = pickle.loads((fixture / 'capture/native' / native_base).read_bytes())
    for index in range(240, 600):
        frame = 100 + index
        time_s = round(index / 20, 5)
        for name in paths:
            row = copy.deepcopy(rows[name][-1])
            if name == 'exception-samples.jsonl':
                row.update(native_frame=frame, time_s=time_s)
            elif name == 'trace.jsonl':
                row.update(frame=frame, time_s=time_s, speed_mps=0, speed_mph=0)
            elif name == 'video_frames.jsonl':
                row.update(video_frame=index, native_frame=frame, carla_frame=frame,
                           time_s=time_s)
            elif name == 'capture/evidence.jsonl':
                row.update(original_frame=frame, replay_frame=frame,
                           recording_time_s=time_s, replay_simulation_time_s=time_s)
                row['ego']['speed_mps'] = 0
            else:
                row.update(frame=frame, time_s=time_s, simulation_time=time_s,
                           base=f'graphs/base/{frame:08d}.pkl',
                           abstract=f'graphs/abstract/{frame:08d}.pkl')
                graph = copy.deepcopy(last_graph)
                graph.graph.update(frame=frame, simulation_time_s=time_s)
                (fixture / 'capture/native' / row['base']).write_bytes(pickle.dumps(graph, protocol=4))
            rows[name].append(row)
    for name in paths:
        (fixture / name).write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                                for row in rows[name]))
    manifest_path = fixture / 'capture/manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['frames'] = 600
    manifest['sources']['trace.jsonl'] = sha(fixture / 'trace.jsonl')
    manifest_path.write_text(json.dumps(manifest) + '\n')


def build(suffix='exception_1_1'):
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
    if ROOT / '.runtime-work' not in output_root.parents:
        raise ValueError('Current diagnostic output root must be under .runtime-work')
    module = importlib.util.spec_from_file_location('exception_probe', HERE / 'probe-package-exception.py')
    probe = importlib.util.module_from_spec(module)
    module.loader.exec_module(probe)
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c10316-d4-recipe-') as temp:
        fixture = Path(temp) / 'fixture'
        probe.fixture_at(fixture, suffix)
        extend_to_600(fixture)
        (fixture / 'road.xodr').write_bytes((HERE / 'native/road.xodr').read_bytes())
        import sys
        sys.path.insert(0, str(HERE / 'native'))
        from exception import measure
        packet_path = fixture / 'statutory-diagnostic-facts.json'
        packet = json.loads(packet_path.read_text())
        packet['source_sha256'] = measure(fixture / 'exception-samples.jsonl', fixture / 'exception-context.json')['source_sha256']
        packet_path.write_text(json.dumps(packet, indent=2) + '\n')
        evidence = [json.loads(line) for line in (fixture / 'capture/evidence.jsonl').read_text().splitlines()]
        for row in evidence:
            row['ego']['speed_provenance'] = 'synthetic_native_sample'
        (fixture / 'capture/evidence.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in evidence))
        trace = [json.loads(line) for line in (fixture / 'trace.jsonl').read_text().splitlines()]
        for row in trace:
            row['velocity_mps'] = [row['speed_mps'], 0.0, 0.0]
        (fixture / 'trace.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in trace))
        capture_manifest = json.loads((fixture / 'capture/manifest.json').read_text())
        capture_manifest['sources']['trace.jsonl'] = sha(fixture / 'trace.jsonl')
        (fixture / 'capture/manifest.json').write_text(json.dumps(capture_manifest, indent=2) + '\n')
        frames = [json.loads(line) for line in (fixture / 'capture/native/frames.jsonl').read_text().splitlines()]
        for row in frames:
            row['base'] = str(Path(row['base']).with_suffix('.adapter.json'))
            row['adapter_graph'] = row['base']
        (fixture / 'capture/native/frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frames))
        files, graphs = {}, []
        for path in sorted(fixture.rglob('*')):
            if not path.is_file() or path.suffix == '.mkv' or path.name == 'road.xodr' or 'channels' in path.relative_to(fixture).parts:
                continue
            relative = path.relative_to(fixture).as_posix()
            if path.suffix == '.pkl':
                graph = pickle.loads(path.read_bytes())
                graphs.append({'path': str(Path(relative).with_suffix('.adapter.json')),
                               'attributes': dict(graph.graph),
                               'nodes': [{'id': node, 'attributes': dict(attrs)}
                                         for node, attrs in graph.nodes(data=True)],
                               'edges': [{'source': start, 'target': end, 'attributes': dict(attrs)}
                                         for start, end, attrs in graph.edges(data=True)]})
            else:
                files[relative] = path.read_text()
        videos = [{'path': name + '.mkv', 'frames': 600, 'width': width, 'height': height,
                   'fps': 20, 'color': 'black'}
                  for name, width, height in (('overview', 1920, 1080),
                                              ('approach', 1280, 720),
                                              ('reference_corner', 1280, 720),
                                              ('driver_reference', 1280, 720))]
        diagnostic = HERE / ('current-' + suffix + '-diagnostic.json')
        diagnostic.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                         separators=(',', ':')) + '\n')
        relative = diagnostic.relative_to(ROOT).as_posix()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': relative,
                               'sha256': sha(diagnostic)}],
                  'generator': {'source': relative, 'sha256': sha(diagnostic)}}
        (HERE / ('current-' + suffix + '-recipe.json')).write_text(json.dumps(recipe, indent=2) + '\n')
        return {'suffix': suffix, 'files': len(files), 'graphs': len(graphs),
                'videos': len(videos), 'diagnostic_bytes': diagnostic.stat().st_size,
                'diagnostic_sha256': sha(diagnostic)}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('exception_1_1', 'exception_1_2'), default='exception_1_1')
    print(json.dumps(build(parser.parse_args().suffix), indent=2))
