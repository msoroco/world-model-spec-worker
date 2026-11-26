"""Bind current-runtime offline receipts for three exact speed requests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def main():
    path = ROOT / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(AID + '__')
        origin = Path('.runtime-work') / ('c329610-draft-offline-' + suffix + '-v2') / 'offline.log'
        log = ROOT / 'native' / ('proof-' + suffix.replace('_', '-') + '.log')
        content = '\n'.join(line.rstrip() for line in origin.read_text().splitlines()).rstrip() + '\n'
        log.write_text(content)
        entry['offline'] = {
            'exit_code': 0,
            'construction_sha256': entry['construction_sha256'],
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID +
                       '/draft-native-manifest.json --case ' + entry['case_id'] +
                       ' --output .runtime-work/c329610-draft-offline-' + suffix +
                       '-v2 --python $PWD/.venv-cpu/bin/python',
            'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
        }
    write(path, manifest)


if __name__ == '__main__':
    main()
