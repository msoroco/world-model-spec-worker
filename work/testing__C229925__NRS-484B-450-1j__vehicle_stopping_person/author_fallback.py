"""Predeclare one same-case early-braking fallback for each halt target."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fire_station_scene import CASES


ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if any(entry.get('compatibility') or entry.get('physical_preparation')
           for entry in manifest['cases']):
        raise ValueError('refusing to overwrite proof-bound manifest')
    for case, entry in zip(CASES, manifest['cases']):
        if entry['case_id'] != case.case_id:
            raise ValueError('exact fallback case order changed')
        primary = json.loads((ROOT / entry['construction']).read_text(encoding='utf-8'))
        fallback = json.loads(json.dumps(primary))
        config_item = next(item for item in fallback['files']
                           if item['path'] == 'config.json')
        config = json.loads(config_item['content'])
        config['engineering_throttle'] = .18
        config['engineering_braking_factor'] = 4.0
        config_item['content'] = json.dumps(config, indent=2) + '\n'
        fallback['mechanisms'] = list(fallback['mechanisms']) + [
            'same exact case with lower approach throttle and earlier braking']
        path = ROOT / 'cases' / case.name / 'fallback1' / 'construction.json'
        write(path, fallback)
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(path.relative_to(ROOT)),
            'construction_sha256': sha(path),
            'trigger': {
                'source': 'original fire-entrance-trace.jsonl and reviewed target',
                'metric': 'terminal ego speed and body-centroid gap over final 2 seconds',
                'failure_condition': 'speed remains above 0.1 m/s or centroid-target gap remains above 1.25 m'},
            'changed_knobs': ['engineering_throttle: 0.25 to 0.18',
                              'engineering_braking_factor: 5.0 to 4.0']}]
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
