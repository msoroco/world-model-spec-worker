"""Retain source-hashed three-outcome CPU physical diagnostics for both cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selected', action='store_true')
    args = parser.parse_args()
    manifest_path = HERE / ('selected-30s-draft-execution-manifest.json' if args.selected
                            else 'current-30s-compatibility-manifest.json')
    manifest = json.loads(manifest_path.read_text())
    base = HERE / ('selected-30s' if args.selected else 'extended-primary') / 'physical-proof'
    index = []
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        folder = base / witness
        folder.mkdir(parents=True, exist_ok=True)
        refs = []
        for kind in KINDS:
            output, log = folder / (kind + '.json'), folder / (kind + '.log')
            command = [sys.executable, str(HERE / 'prove-30s-physical.py'),
                       '--witness', witness, '--kind', kind, '--output', str(output),
                       '--manifest', str(manifest_path)]
            with log.open('w', encoding='utf-8') as stream:
                result = subprocess.run(command, cwd=REPO, stdout=stream,
                                        stderr=subprocess.STDOUT, timeout=30)
            if result.returncode:
                raise ValueError(f'Physical diagnostic failed: {log}')
            refs.append({'kind': kind, 'command': ' '.join(command), 'exit_code': 0,
                         'log': log.relative_to(HERE).as_posix(), 'log_sha256': sha(log),
                         'result': output.relative_to(HERE).as_posix(),
                         'result_sha256': sha(output)})
        life = json.loads((folder / 'lifecycle.json').read_text())
        proof = {'format': 'c422978-30s-synthetic-physical-preparation-v1',
                 'case_id': entry['case_id'],
                 'construction_sha256': entry['construction_sha256'],
                 'fixtures': refs[:3],
                 'lifecycle': {**life, 'log': refs[3]['log'],
                               'log_sha256': refs[3]['log_sha256']},
                 'diagnostic_only': True, 'original_native_observed': False}
        path = folder / 'proof.json'
        write(path, proof)
        index.append({'case_id': entry['case_id'],
                      'receipt': path.relative_to(HERE).as_posix(),
                      'sha256': sha(path)})
    index_path = base / 'index.json'
    write(index_path, {'format': 'c422978-30s-physical-index-v1',
                       'cases': index, 'diagnostic_only': True})
    print(json.dumps({'physical_fixture_cases': len(index), 'index_sha256': sha(index_path)}))


if __name__ == '__main__':
    main()
