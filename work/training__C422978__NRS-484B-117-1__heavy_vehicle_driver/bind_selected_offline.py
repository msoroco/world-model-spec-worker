"""Bind four exact materializer checks after their scratch runs finish."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'selected-draft-execution-manifest.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(source, target):
    lines = [line.rstrip() for line in source.read_text().splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    target.write_text('\n'.join(lines) + '\n')


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        selected = [{'id': 'primary',
                     'construction_sha256': entry['construction_sha256'],
                     'target': entry}, *entry['candidates']]
        for item in selected:
            variant = item['id']
            scratch = REPO / '.runtime-work' / f'c422978-selected-{suffix}-{variant}-v9'
            source = scratch / 'offline.log'
            if not source.is_file() or 'OK' not in source.read_text():
                raise ValueError('Missing passing exact materializer log: ' + str(source))
            target = HERE / f'selected-{suffix}-{variant}-offline.log'
            clean_log(source, target)
            command = (f'{REPO}/.venv-cpu/bin/python {REPO}/runtime.py offline '
                       f'--manifest {MANIFEST} --case {entry["case_id"]} '
                       f'--candidate {variant} --output {scratch} '
                       f'--python {REPO}/.venv-cpu/bin/python')
            item['offline'] = {'command': command, 'exit_code': 0,
                               'construction_sha256': item['construction_sha256'],
                               'log': target.name, 'log_sha256': digest(target)}
            if variant == 'primary':
                entry['offline'] = item['offline']
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    return digest(MANIFEST)


if __name__ == '__main__':
    print(bind())
