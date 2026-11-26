"""Run pinned public compatibility for both parked cases and both candidates."""
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
        for candidate in ('primary', 'fallback1'):
            output = SCRATCH/'parked-compat'/suffix/candidate
            if suffix == 'parked_lamps_1' and candidate == 'primary':
                output = SCRATCH/'parked-1-primary-compat-v1'
            receipt_path = output/'compatibility.json'
            if not receipt_path.is_file():
                if output.exists():
                    raise RuntimeError('partial compatibility output exists: '+str(output))
                command = [str(ROOT/'.venv-cpu/bin/python'), '-B', str(ROOT/'runtime.py'),
                           'compatibility', '--manifest', str(MANIFEST),
                           '--case', entry['case_id'], '--candidate', candidate,
                           '--output', str(output), '--library', str(ROOT/'runtime/library'),
                           '--validator', str(SCRATCH/'decoder/.lake/build/bin/adapterCheck')]
                command_log = SCRATCH/'parked-compat'/suffix/(candidate+'-command.log')
                command_log.parent.mkdir(parents=True, exist_ok=True)
                with command_log.open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, env=environment,
                                            stdout=stream, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f'{suffix}/{candidate} compatibility failed; see {command_log}')
            receipt = json.loads(receipt_path.read_text())
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            assert (receipt['passed'] and receipt['case_id'] == entry['case_id'] and
                    receipt['candidate_id'] == candidate and
                    receipt['construction_sha256'] == selected['construction_sha256'] and
                    receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'])
            target = HERE/'draft-parked-proofs'/suffix/candidate
            target.mkdir(parents=True, exist_ok=True)
            for name, source in (('receipt.json', receipt_path),
                                 ('analysis.log', output/'compatibility-analysis.log'),
                                 ('negative.log', output/'negative-analysis.log')):
                shutil.copy2(source, target/name)
            rows.append({'case_id': entry['case_id'], 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'receipt': (target/'receipt.json').relative_to(HERE).as_posix(),
                         'receipt_sha256': sha(target/'receipt.json'),
                         'passed': True, 'physical_acceptance_claimed': False})
            print(json.dumps(rows[-1], sort_keys=True), flush=True)
    summary = {'format': 'c179824-parked-compatibility-proof-v1', 'cases': rows,
               'all_passed': len(rows) == 4 and all(row['passed'] for row in rows),
               'physical_acceptance_claimed': False}
    (HERE/'draft-parked-compatibility-receipt.json').write_text(json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
