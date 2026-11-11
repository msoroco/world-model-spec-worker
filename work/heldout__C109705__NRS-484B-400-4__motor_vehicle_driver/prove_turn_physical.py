"""Bind synthetic physical outcomes and ordered lifecycle for six exact turns."""

from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'probe-compatibility-manifest.json'
OUT = HERE / 'physical'
EVENTS = ['capture_finished', 'encoders_closed', 'restoration_verified',
          'native_exit', 'owner_released', 'saved_processing_started']


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def call(command, log):
    with log.open('w') as target:
        result = subprocess.run(command, cwd=ROOT, stdout=target,
                                stderr=subprocess.STDOUT)
    if result.returncode:
        raise ValueError(log.read_text())


def main():
    OUT.mkdir(exist_ok=True)
    records = []
    for entry in json.loads(MANIFEST.read_text())['cases']:
        case = entry['case_id']
        slug = case.split('__')[-1]
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            result = OUT / (slug + '-' + kind + '.json')
            log = OUT / (slug + '-' + kind + '.log')
            command = [sys.executable, str(HERE / 'turn_physical_fixture.py'),
                       '--case', case, '--kind', kind, '--output', str(result)]
            call(command, log)
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': str(log.relative_to(HERE)),
                             'log_sha256': digest(log),
                             'result': str(result.relative_to(HERE)),
                             'result_sha256': digest(result)})
        life_log = OUT / (slug + '-lifecycle.log')
        life_command = [sys.executable, str(HERE / 'turn_lifecycle_fixture.py'),
                        '--case', case]
        call(life_command, life_log)
        if ' '.join(EVENTS) not in life_log.read_text():
            raise ValueError('Turn lifecycle ordering differs: ' + slug)
        proof = {'construction_sha256': entry['construction_sha256'],
                 'fixture_scope': 'Synthetic Native-shaped turn source protocol only',
                 'fixtures': fixtures,
                 'lifecycle': {'events': EVENTS, 'exit_code': 0,
                               'command': ' '.join(life_command),
                               'log': str(life_log.relative_to(HERE)),
                               'log_sha256': digest(life_log)}}
        receipt = OUT / (slug + '-proof.json')
        receipt.write_text(json.dumps(proof, indent=2) + '\n')
        records.append({'case_id': case, 'receipt': str(receipt.relative_to(HERE)),
                        'sha256': digest(receipt)})
        print(slug, 'three synthetic outcomes and ordered lifecycle passed', flush=True)
    (HERE / 'turn-physical-proofs.json').write_text(json.dumps(records, indent=2) + '\n')


if __name__ == '__main__':
    main()
