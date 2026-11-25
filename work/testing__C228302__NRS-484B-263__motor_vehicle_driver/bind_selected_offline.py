"""Bind successful exact selected offline logs without rewriting constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(HERE.name + '__')
        log = HERE / ('cpu-nov25-selected-offline-' + name + '.log')
        if not log.is_file() or not json.loads(log.read_text()).get('offline_passed'):
            raise ValueError('selected offline proof missing: ' + name)
        entry['offline']['exit_code'] = 0
        entry['offline']['log_sha256'] = sha(log)
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
