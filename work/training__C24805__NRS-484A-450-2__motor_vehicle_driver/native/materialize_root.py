"""Expose one exact primary at the canonical assignment root for static review."""

import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]


def main():
    source = HERE / 'selected-probe_a-primary-construction.json'
    body = json.loads(source.read_text())
    for item in body['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(body, indent=2,
                                                      ensure_ascii=False) + '\n')
    print('Materialized', body['case_id'])


if __name__ == '__main__':
    main()
