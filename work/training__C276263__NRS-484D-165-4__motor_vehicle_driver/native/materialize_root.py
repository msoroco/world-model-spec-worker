"""Materialize the selected first case at the canonical package root."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    source = ROOT / 'selected-probe_a-construction.json'
    construction = json.loads(source.read_text())
    (ROOT / 'construction.json').write_text(source.read_text())
    for item in construction['files']:
        path = ROOT / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    print(json.dumps({'root_case': construction['case_id'],
                      'files': len(construction['files'])}))


if __name__ == '__main__':
    main()
