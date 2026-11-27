"""Bind exact current-runtime offline proof logs to draft manifest."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / ('c245490_offline_v2_' + suffix) / 'offline.log'
        if not source.is_file() or 'OK' not in source.read_text():
            raise ValueError('Exact offline proof missing: ' + suffix)
        target = HERE / ('native-proof-' + suffix + '.log')
        target.write_text(source.read_text().rstrip() + '\n')
        entry['offline'] = {'command': '.venv-cpu/bin/python -B runtime.py offline '
            '--manifest work/' + HERE.name + '/draft-native-manifest.json --case '
            + entry['case_id'] + ' --output .runtime-work/c245490_offline_v2_' + suffix
            + ' --python "$PWD/.venv-cpu/bin/python"',
            'construction_sha256': entry['construction_sha256'],
            'exit_code': 0, 'log': target.name, 'log_sha256': sha(target)}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    return {'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
