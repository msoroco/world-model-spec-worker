"""Freeze small textual Native-shaped diagnostics for the current recipe runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
loader = importlib.util.spec_from_file_location('probe_portable', HERE / 'probe-portable.py')
module = importlib.util.module_from_spec(loader)
loader.loader.exec_module(module)
fixture = module.fixture


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for suffix in ('condition_a', 'condition_b'):
        with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work') as temporary:
            source = Path(temporary) / 'fixture'
            fixture(source, suffix)
            files = {}
            for path in source.rglob('*'):
                if path.is_file() and path.suffix != '.mkv' and '/graphs/' not in str(path):
                    files[str(path.relative_to(source))] = path.read_text()
            graphs = []
            for index in range(480):
                frame = 100 + index
                graphs.append({'path': f'capture/native/graphs/base/{frame:08d}.adapter.json',
                               'attributes': {'frame': frame}, 'nodes': [], 'edges': []})
            frames = [json.loads(line) for line in files['capture/native/frames.jsonl'].splitlines()]
            for frame in frames:
                stem = f"graphs/base/{frame['frame']:08d}.adapter.json"
                frame.update(base=stem, abstract=stem, adapter_graph=stem,
                             nodes=0, edges=0)
            files['capture/native/frames.jsonl'] = ''.join(
                json.dumps(frame, sort_keys=True) + '\n' for frame in frames)
            videos = [{'path': name + '.mkv', 'frames': 480, 'width': width,
                       'height': height, 'fps': 20, 'color': 'black'}
                      for name, width, height in
                      (('overview', 1920, 1080), ('approach', 1280, 720),
                       ('reference_corner', 1280, 720), ('driver_reference', 1280, 720))]
            spec = HERE / ('diagnostic-' + suffix + '.json')
            spec.write_text(json.dumps({'files': files, 'graphs': graphs,
                                        'videos': videos}, separators=(',', ':')) + '\n')
            assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
            recipe = HERE / ('diagnostic-' + suffix + '-recipe.json')
            recipe.write_text(json.dumps({
                'format': 'worker-fixture-recipe',
                'sources': [{'path': 'diagnostic-input-assignment.json',
                             'source': str(assignment.relative_to(ROOT)),
                             'sha256': sha(assignment)}],
                'generator': {'source': str(spec.relative_to(ROOT)),
                              'sha256': sha(spec)}}, indent=2) + '\n')
            print(suffix, spec.stat().st_size, sha(spec))


if __name__ == '__main__':
    main()
