"""Bind three exact current-runtime offline receipts after immutable construction."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        speed = entry['case_id'].rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / ('c230281-offline-selected-v3-' + speed) / 'offline.log'
        if not source.is_file():
            raise ValueError('Missing selected offline proof: ' + speed)
        target = HERE / ('selected-' + speed + '-offline.log')
        target.write_text(source.read_text().rstrip() + '\n')
        entry['offline'] = {'command': 'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c230281-owner TMPDIR=.runtime-work .venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID + '/draft-native-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/c230281-offline-selected-v3-' + speed,
            'construction_sha256': entry['construction_sha256'],
            'exit_code': 0, 'log': target.name, 'log_sha256': sha(target)}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'offline': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
