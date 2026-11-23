"""Inventory the existing synthetic saved sources as a reproducible CPU fixture."""
import json
import hashlib
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
ROOT = PACKAGE.parents[1]
SOURCE = ROOT / '.runtime-work/c229597-saved-v7/attempt'
OUTPUT = PACKAGE / 'selected-reference-fixture.json'


def main():
    files = {}
    graphs = []
    for path in sorted(SOURCE.rglob('*')):
        if not path.is_file() or path.suffix == '.mkv' or path.name in ('config.json', 'construction.json'):
            continue
        relative = path.relative_to(SOURCE).as_posix()
        if relative.startswith('capture/native/graphs/'):
            data = json.loads(path.read_text())
            graphs.append({'path': relative, 'attributes': data['metadata'],
                           'nodes': data['nodes'], 'edges': data['edges']})
        else:
            files[relative] = path.read_text()
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
    evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
    if len(trace) != 600 or len(evidence) != 600 or len(graphs) != 600:
        raise ValueError('Expected 600 source-aligned synthetic samples')
    x = 0.0
    for index, (motion, event, graph) in enumerate(zip(trace, evidence, graphs)):
        if index:
            x += (motion['velocity_mps'][0] + trace[index - 1]['velocity_mps'][0]) / 40
        center = [x, 0.0, 0.0]
        box = [[x + dx, dy, z] for dx in (-2., 2.)
               for dy in (-.8, .8) for z in (0., 1.5)]
        motion['position_m'] = center
        motion['position'] = {'x': x, 'y': 0.0, 'z': 0.0}
        event['ego']['position_m'] = center
        event['ego']['body_vertices_m'] = box
        event['world']['road_projection']['s_m'] = x
        graph['nodes'][0]['attributes']['vertex'] = center
        graph['nodes'][0]['attributes']['threedbbox'] = box
    files['trace.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in trace)
    files['capture/evidence.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in evidence)
    files['road.xodr'] = files['road.xodr'].replace('east="200"', 'east="300"').replace('length="200"', 'length="300"')
    manifest = json.loads(files['capture/manifest.json'])
    for name in ('trace.jsonl', 'road.xodr'):
        manifest['sources'][name] = hashlib.sha256(files[name].encode()).hexdigest()
    files['capture/manifest.json'] = json.dumps(manifest, separators=(',', ':')) + '\n'
    videos = [{'path': name + '.mkv', 'frames': 600, 'width': width,
               'height': height, 'fps': 20, 'color': 'black'}
              for name, width, height in [('overview', 1920, 1080),
                                          ('approach', 1280, 720),
                                          ('reference_corner', 1280, 720),
                                          ('driver_reference', 1280, 720)]]
    OUTPUT.write_text(json.dumps({'files': files, 'graphs': graphs, 'videos': videos},
                                 separators=(',', ':'), allow_nan=False) + '\n')
    print(json.dumps({'files': len(files), 'graphs': len(graphs),
                      'bytes': OUTPUT.stat().st_size}))


if __name__ == '__main__':
    main()
