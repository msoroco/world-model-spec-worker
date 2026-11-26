"""Bind current exact-case selected and fallback offline proof logs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        name = case.removeprefix(AID + '__')
        selected_log = HERE / ('cpu-nov26-selected-offline-' + name + '.log')
        fallback_log = HERE / ('cpu-nov26-fallback-offline-' + name + '.log')
        for log, candidate_id in ((selected_log, 'primary'), (fallback_log, 'fallback1')):
            if not log.is_file() or '"offline_passed": true' not in log.read_text():
                raise ValueError(name + ': offline proof missing: ' + candidate_id)
            construction = (entry if candidate_id == 'primary' else entry['candidates'][0])
            output = ('selected' if candidate_id == 'primary' else 'fallback') + '-offline-' + name + '-v8'
            command = ('.venv-cpu/bin/python runtime.py offline --manifest work/' + AID +
                       '/execution-manifest.json --case ' + case +
                       (' --candidate fallback1' if candidate_id == 'fallback1' else '') +
                       ' --output .runtime-work/c150116-new/' + output)
            construction['offline'] = {'command': command, 'exit_code': 0,
                                       'construction_sha256': construction['construction_sha256'],
                                       'log': log.name, 'log_sha256': sha(log)}
    path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
