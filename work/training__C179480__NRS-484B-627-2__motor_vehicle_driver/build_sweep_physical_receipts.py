"""Bind each qualified sweep construction to three synthetic physical outcomes."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ('complete_motion', 'incomplete_motion', 'missing_evidence')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build():
    manifest = json.loads((HERE / 'sweep-candidate-manifest.json').read_text())
    life = HERE / 'update160-lifecycle.log'
    events = json.loads(life.read_text())['events']
    if events != ['capture_finished', 'encoders_closed', 'restoration_verified',
                  'native_exit', 'owner_released', 'saved_processing_started']:
        raise ValueError('Synthetic lifecycle proof differs')
    output = HERE / 'sweep-physical-fixtures'
    output.mkdir(exist_ok=True)
    rows = []
    for entry in manifest['cases']:
        cid = entry['case_id']
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('Primary sweep construction changed: ' + cid)
        fixtures = []
        for kind in KINDS:
            result = output / f'{cid}-{kind}.json'
            log = output / f'{cid}-{kind}.log'
            command = [sys.executable, str(HERE / 'physical_sweep_diagnostic.py'),
                       '--case', cid, '--kind', kind, '--output', str(result)]
            with log.open('w') as stream:
                completed = subprocess.run(command, cwd=ROOT, stdout=stream,
                                           stderr=subprocess.STDOUT)
            if completed.returncode:
                raise ValueError(f'Physical fixture failed: {cid}/{kind}: {log.read_text()[-700:]}')
            fixtures.append({'kind': kind, 'command': ' '.join(command),
                             'exit_code': 0, 'log': str(log.relative_to(HERE)),
                             'log_sha256': sha(log), 'result': str(result.relative_to(HERE)),
                             'result_sha256': sha(result)})
        receipt = {'format': 'c179480-sweep-physical-preparation-cpu-v1',
                   'case_id': cid, 'construction_sha256': entry['construction_sha256'],
                   'fixtures': fixtures,
                   'lifecycle': {'events': events, 'exit_code': 0,
                                 'log': str(life.relative_to(HERE)),
                                 'log_sha256': sha(life)},
                   'scope': 'synthetic physical-stop and fake-world lifecycle only',
                   'actual_native_or_legal_acceptance_claimed': False}
        target = HERE / f'sweep-qualified-{cid}-physical-receipt.json'
        write(target, receipt)
        rows.append({'case_id': cid, 'receipt': target.name, 'sha256': sha(target),
                     'construction_sha256': entry['construction_sha256']})
    index = HERE / 'sweep-qualified-physical-index.json'
    write(index, {'format': 'c179480-sweep-physical-receipts-index-v1',
                  'receipts': rows, 'selected_delivery_manifest_bound': False})
    return {'cases': len(rows), 'index': index.name, 'index_sha256': sha(index)}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2, sort_keys=True))
