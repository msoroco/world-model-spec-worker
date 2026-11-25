"""Bind exact current-runtime selected offline checks to source hashes."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    target = FOLDER/'execution-manifest.json'
    manifest = json.loads(target.read_text())
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        for candidate_id, choice in [('primary', entry),
                                     ('fallback1', entry['candidates'][0])]:
            output = REPO/'.runtime-work'/f'c111325-final-offline-{condition}-{candidate_id}'
            source = output/'offline.log'
            if not source.is_file() or not json.loads(source.read_text().splitlines()[0])['passed']:
                raise ValueError('Selected offline proof missing: '+condition+' '+candidate_id)
            rel_log = f'selected-offline-{condition}-{candidate_id}.log'
            log = FOLDER/rel_log
            log.write_text(source.read_text().rstrip()+'\n')
            command = ('.venv-cpu/bin/python runtime.py offline --manifest '
                       +str(target.relative_to(REPO))+' --case '+entry['case_id']
                       +' --candidate '+candidate_id+' --output '
                       +str(output.relative_to(REPO)))
            choice['offline'] = {'command': command, 'exit_code': 0,
                                 'construction_sha256': choice['construction_sha256'],
                                 'log': rel_log, 'log_sha256': sha(log)}
    target.write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'offline_bound': 4, 'manifest_sha256': sha(target)}))


if __name__ == '__main__':
    main()
