"""Inventory the existing synthetic saved sources as a reproducible CPU fixture."""
import json
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
