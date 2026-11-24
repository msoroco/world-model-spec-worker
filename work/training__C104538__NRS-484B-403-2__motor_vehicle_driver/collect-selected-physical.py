"""Record three source-shaped motion branches and lifecycle CPU proofs."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2)+'\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        folder = HERE / 'physical-proof' / case
        folder.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion','incomplete_motion','missing_evidence'):
            result = folder / (kind+'.json')
            log = folder / (kind+'.log')
            command = [str(ROOT / '.venv-cpu/bin/python'), str(HERE / 'prove-selected-physical.py'),
                       '--case', case, '--kind', kind, '--output', str(result)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            log.write_text((completed.stdout+completed.stderr).rstrip()+'\n')
            if completed.returncode:
                raise RuntimeError(log.read_text())
            fixtures.append({'kind':kind, 'command':' '.join(command), 'exit_code':0,
                             'log':str(log.relative_to(HERE)), 'log_sha256':sha(log),
                             'result':str(result.relative_to(HERE)), 'result_sha256':sha(result)})
        log = folder / 'lifecycle.log'
        command = [str(ROOT / '.venv-cpu/bin/python'),str(HERE / 'prove-selected-physical.py'),
                   '--case',case,'--kind','lifecycle','--output',str(ROOT/'.runtime-work/c104538-unused.json')]
        completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
        log.write_text((completed.stdout+completed.stderr).rstrip()+'\n')
        if completed.returncode:
            raise RuntimeError(log.read_text())
        lifecycle = {'events':['capture_finished','encoders_closed','restoration_verified',
                               'native_exit','owner_released','saved_processing_started'],
                     'exit_code':0,'log':str(log.relative_to(HERE)),'log_sha256':sha(log)}
        proof = {'format':'c104538-synthetic-physical-preparation-v1',
                 'case_id':entry['case_id'], 'construction_sha256':entry['construction_sha256'],
                 'fixtures':fixtures,'lifecycle':lifecycle,
                 'original_native_observed':False,'physical_acceptance_claimed':False}
        receipt = folder / 'proof.json'
        write(receipt, proof)
        entry['physical_preparation'] = {'receipt':str(receipt.relative_to(HERE)), 'sha256':sha(receipt)}
    write(manifest_path,manifest)
    print(json.dumps({'cases':len(manifest['cases']),'manifest_sha256':sha(manifest_path)}))


if __name__ == '__main__':
    main()
