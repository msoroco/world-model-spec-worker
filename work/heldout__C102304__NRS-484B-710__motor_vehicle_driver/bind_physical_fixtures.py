"""Bind tested synthetic motion outcomes to exact candidate construction hashes."""
import hashlib
import json
from pathlib import Path
import subprocess

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
manifest_path = folder / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
output = folder / 'physical'
output.mkdir(exist_ok=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case = entry['case_id']
    stem = case.split('__')[-1]
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = output / (stem + '-' + kind + '.json')
        log = output / (stem + '-' + kind + '.log')
        command = '.venv-cpu/bin/python work/' + folder.name + '/physical_fixture.py --case ' + case + ' --kind ' + kind + ' --output work/' + folder.name + '/physical/' + result.name
        run = subprocess.run(command.split(), cwd=repo, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, text=True, check=False)
        log.write_text(run.stdout)
        if run.returncode != 0:
            raise ValueError(f'{case} {kind} failed: {run.stdout[-700:]}')
        fixtures.append({'kind': kind, 'command': command, 'exit_code': run.returncode,
                         'log': str(log.relative_to(folder)), 'log_sha256': sha(log),
                         'result': str(result.relative_to(folder)), 'result_sha256': sha(result)})
    lifecycle_log = folder / 'cpu-tests.log'
    proof = {'construction_sha256': entry['construction_sha256'],
             'fixture_scope': 'Synthetic Native-shaped source protocol only; no actual capture or visible-body finding',
             'fixtures': fixtures,
             'lifecycle': {
                 'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                            'native_exit', 'owner_released', 'saved_processing_started'],
                 'exit_code': 0, 'log': 'cpu-tests.log', 'log_sha256': sha(lifecycle_log),
                 'test_scope': 'Assignment runner restoration and saved-only processing tests; actual operator release remains to be verified'}}
    receipt = output / (stem + '-proof.json')
    receipt.write_text(json.dumps(proof, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': str(receipt.relative_to(folder)),
                                     'sha256': sha(receipt)}
manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
print('Bound three synthetic physical outcomes for', len(manifest['cases']), 'exact cases')
