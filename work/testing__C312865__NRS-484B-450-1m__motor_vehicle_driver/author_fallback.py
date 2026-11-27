"""Author a slower earlier-braking physical fallback for each exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        primary_path = ROOT / entry['construction']
        primary = json.loads(primary_path.read_text(encoding='utf-8'))
        entry['construction_sha256'] = sha(primary_path)
        entry.pop('offline', None)
        entry.pop('compatibility', None)
        entry.pop('negative', None)
        fallback = json.loads(json.dumps(primary))
        config_entry = next(item for item in fallback['files'] if item['path'] == 'config.json')
        config = json.loads(config_entry['content'])
        config['engineering_throttle'] = 0.18
        config['engineering_braking_factor'] = 4.0
        config_entry['content'] = json.dumps(config, indent=2) + '\n'
        path = Path('cases') / suffix / 'fallback1-construction.json'
        write(ROOT / path, fallback)
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': str(path),
            'construction_sha256': sha(ROOT / path),
            'trigger': {
                'source': 'original Native trace.jsonl and tunnel-history.jsonl',
                'metric': 'terminal halt readback and source-bound full-body tunnel relation',
                'failure_condition': 'primary does not reach a stable terminal halt or tunnel body relation is not observable'},
            'changed_knobs': ['engineering_throttle: 0.25 to 0.18',
                              'engineering_braking_factor: 5.0 to 4.0']
        }]
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
