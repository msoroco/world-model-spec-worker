"""Process every exact parked primary's saved diagnostic sources only."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT/'.runtime-work/c179824'
MANIFEST = HERE/'draft-parked-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    environment = os.environ.copy()
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    environment['TMPDIR'] = str(SCRATCH)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name+'__')
        attempt = (SCRATCH/'parked-1-primary-compat-v1' if suffix == 'parked_lamps_1'
                   else SCRATCH/'parked-compat'/suffix/'primary')
        compatibility = json.loads((attempt/'compatibility.json').read_text())
        assert compatibility['passed'] and compatibility['construction_sha256'] == entry['construction_sha256']
        output = SCRATCH/'parked-saved'/suffix
        receipt_path = output/'v0001/processing.json'
        if not receipt_path.is_file():
            command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                       'process-saved', '--manifest', str(MANIFEST),
                       '--case', entry['case_id'], '--attempt', str(attempt),
                       '--output', str(output), '--library', str(ROOT/'runtime/library'),
                       '--validator', str(SCRATCH/'decoder/.lake/build/bin/adapterCheck')]
            log = SCRATCH/'parked-saved'/suffix/'command.log'
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, env=environment,
                                        stdout=stream, stderr=subprocess.STDOUT)
            if result.returncode:
                raise RuntimeError(f'{suffix} recorded-only saved proof failed; see {log}')
        receipt = json.loads(receipt_path.read_text())
        assert (receipt['passed'] and receipt['recorded_only'] and
                receipt['candidate_id'] == 'primary' and
                receipt['timestamp_joins']['passed'] and
                receipt['timestamp_joins']['frames'] == 600 and
                not receipt['missing_evidence'] and receipt['originals_preserved'] and
                not receipt['physical_acceptance_claimed'] and
                not receipt['legal_acceptance_claimed'])
        target = HERE/'draft-parked-proofs'/suffix/'primary/saved-processing.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(receipt_path, target)
        rows.append({'case_id': entry['case_id'], 'candidate': 'primary',
                     'saved_receipt': target.relative_to(HERE).as_posix(),
                     'saved_receipt_sha256': sha(target), 'passed': True,
                     'recorded_only': True, 'original_native_observed': False})
        print(json.dumps(rows[-1], sort_keys=True), flush=True)
    summary = {'format': 'c179824-parked-saved-proof-v1', 'cases': rows,
               'all_passed': len(rows) == 2 and all(row['passed'] for row in rows),
               'original_native_observed': False}
    (HERE/'draft-parked-saved-receipt.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
