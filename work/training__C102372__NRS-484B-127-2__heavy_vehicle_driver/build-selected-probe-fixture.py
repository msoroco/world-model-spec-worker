"""Freeze the existing 600-frame probe diagnostic as a portable text recipe."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / '.runtime-work/c102372-current-saved-probe1-pair/source-build/fixture'
DEST = HERE / 'selected-fixture/probe_1'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def main() -> None:
    if not SOURCE.is_dir():
        raise FileNotFoundError('Retained source-bound probe diagnostic missing')
    DEST.mkdir(parents=True, exist_ok=True)
    files = {}
    graphs = []
    for source in sorted(SOURCE.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(SOURCE).as_posix()
        if relative.endswith('.mkv'):
            continue
        if relative.startswith('channels/') or relative in (
            'fallback-metrics.json', 'trigger-source-manifest.json'):
            continue
        if relative.startswith('capture/native/graphs/'):
            packet = json.loads(source.read_text())
            if packet.get('format') != 'native-adapter-graph-v1':
                raise ValueError('Retained graph is not a live adapter packet')
            graphs.append({'path': relative, 'attributes': packet['metadata'],
                           'nodes': packet['nodes'], 'edges': packet['edges']})
            continue
        target = DEST / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        files[relative] = {'path': relative,
                           'source': target.relative_to(ROOT).as_posix(),
                           'sha256': digest(target)}
    if len(graphs) != 600:
        raise ValueError('Selected probe requires 600 original frame packets')
    native = [json.loads(line) for line in (DEST / 'native_samples.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (DEST / 'trace.jsonl').read_text().splitlines()]
    if len(native) != 600 or len(trace) != 600:
        raise ValueError('Selected source trace must cover all 600 Native frames')
    for measured, row in zip(native, trace):
        row['velocity_mps'] = [measured['ego']['speed_mps'], 0.0, 0.0]
        row['synthetic_diagnostic'] = True
    (DEST / 'trace.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n'
                                             for row in trace))
    capture = json.loads((DEST / 'capture/manifest.json').read_text())
    capture['sources']['trace.jsonl'] = digest(DEST / 'trace.jsonl')
    write_json(DEST / 'capture/manifest.json', capture)
    for relative in ('trace.jsonl', 'capture/manifest.json'):
        files[relative]['sha256'] = digest(DEST / relative)
    construction = json.loads((HERE / 'draft-candidates/probe_1/primary/construction.json').read_text())
    config = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'config.json'))
    camera = {item['name']: item for item in config['cameras']}
    videos = [{'path': name + '.mkv', 'frames': 600,
               'width': camera[name]['width'], 'height': camera[name]['height'],
               'fps': 20, 'color': 'black'} for name in CAMERAS]
    specification = DEST / 'generator.json'
    write_json(specification, {'files': {}, 'graphs': graphs, 'videos': videos})
    recipe = {'format': 'worker-fixture-recipe',
              'sources': [files[name] for name in sorted(files)],
              'generator': {'source': specification.relative_to(ROOT).as_posix(),
                            'sha256': digest(specification)}}
    write_json(DEST / 'recipe.json', recipe)
    contract = json.loads((HERE / 'native/measurement-contract-probe_1.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    write_json(DEST / 'measurement-contract.json', contract)
    print(json.dumps({'sources': len(files), 'graphs': len(graphs),
                      'generator_bytes': specification.stat().st_size,
                      'recipe_sha256': digest(DEST / 'recipe.json')}, sort_keys=True))


if __name__ == '__main__':
    main()
