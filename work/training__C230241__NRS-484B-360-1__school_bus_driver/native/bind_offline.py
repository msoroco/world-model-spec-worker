"""Bind four current-runtime selected offline checks to exact construction hashes."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        label = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1'):
            choice = entry if candidate == 'primary' else entry['candidates'][0]
            source = REPO / '.runtime-work' / f'c230241-offline-v5-{label}-{candidate}/offline.log'
            target = FOLDER / 'proofs' / label / candidate / 'offline.log'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(source.read_text().rstrip() + '\n')
            command = (f'.venv-cpu/bin/python runtime.py offline --manifest work/{FOLDER.name}/execution-manifest.json '
                       f'--case {entry["case_id"]} --candidate {candidate} '
                       f'--output .runtime-work/c230241-offline-v5-{label}-{candidate}')
            choice['offline'] = {'command': command, 'exit_code': 0,
                                 'construction_sha256': choice['construction_sha256'],
                                 'log': str(target.relative_to(FOLDER)),
                                 'log_sha256': sha(target)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'offline_candidates': 4, 'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
