"""Bind surveyed alternate bus spawn without changing wheel-gap comparison."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        primary_path = HERE / entry['construction']
        primary = json.loads(primary_path.read_text())
        config = json.loads(next(item['content'] for item in primary['files']
                                 if item['path'] == 'config.json'))
        assert config['bus_spawn_x_m'] == -20
        alternate = json.loads(primary_path.read_text())
        other = dict(config)
        other['candidate_id'] = 'fallback1'
        other['bus_spawn_x_m'] = -25
        config_file = next(item for item in alternate['files']
                           if item['path'] == 'config.json')
        config_file['content'] = json.dumps(other, indent=2) + '\n'
        path = HERE / 'draft-exact' / suffix / 'fallback1' / 'construction.json'
        write(path, alternate)
        entry['candidates'] = [{'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native bus spawn receipt',
                'metric': 'primary_bus_spawn_failed',
                'failure_condition': 'primary -20 m bus spawn is occupied or fails placement'},
            'changed_knobs': ['surveyed bus spawn x -20 m to -25 m before same curb zone']}]
        if suffix == 'probe_1':
            write(HERE / 'construction.json', primary)
            for item in primary['files']:
                materialized = HERE / item['path']
                materialized.parent.mkdir(parents=True, exist_ok=True)
                materialized.write_text(item['content'])
    write(HERE / 'selected-offline-manifest.json', manifest)
    print([(e['case_id'], len(e['candidates'])) for e in manifest['cases']])


if __name__ == '__main__':
    main()
