"""Run and bind four physical/lifecycle CPU fixture outcomes per selected case."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
SCRIPT = ROOT / 'native/prove_physical.py'
SHORTS = ('controlled_1', 'controlled_2', 'pedestrian_clearance',
          'pedestrian_overlap', 'concurrent_absent', 'concurrent_present')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    for short in SHORTS:
        folder = ROOT / 'physical' / short
        folder.mkdir(parents=True, exist_ok=True)
        construction = ROOT / f'native/selected-{short}-primary-construction.json'
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence', 'lifecycle'):
            target = folder / f'{kind}.json'
            command = ['.venv-cpu/bin/python', str(SCRIPT.relative_to(REPO)),
                       '--case', short, '--kind', kind,
                       '--output', str(target.relative_to(REPO))]
            proc = subprocess.run(command, cwd=REPO, capture_output=True, text=True)
            log = folder / f'{kind}.log'
            log.write_text((proc.stdout + proc.stderr).rstrip() + '\n')
            if proc.returncode:
                raise RuntimeError(f'{short} {kind}: {proc.stderr}')
            if kind == 'lifecycle':
                lifecycle = {'events': json.loads(target.read_text())['events'],
                             'exit_code': proc.returncode,
                             'log': str(log.relative_to(ROOT)),
                             'log_sha256': sha(log)}
            else:
                fixtures.append({'kind': kind, 'command': ' '.join(command),
                                 'log': str(log.relative_to(ROOT)),
                                 'log_sha256': sha(log), 'exit_code': proc.returncode,
                                 'result': str(target.relative_to(ROOT)),
                                 'result_sha256': sha(target)})
        receipt = {'format': 'worker-physical-preparation-proof',
                   'case_id': json.loads(construction.read_text())['case_id'],
                   'construction_sha256': sha(construction),
                   'fixtures': fixtures, 'lifecycle': lifecycle,
                   'scope': 'synthetic fixture only; original Native and legal review pending'}
        (folder / 'proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
        print(short, 'physical fixtures passed')


if __name__ == '__main__':
    main()
