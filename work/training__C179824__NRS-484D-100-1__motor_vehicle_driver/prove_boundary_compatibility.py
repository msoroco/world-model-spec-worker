"""Run each exact boundary candidate through pinned public compatibility."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT/'.runtime-work/c179824'
MANIFEST = HERE/'draft-boundary-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    environment = os.environ.copy()
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
    environment['TMPDIR'] = str(SCRATCH)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    proof_rows = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name+'__')
        recipe = HERE/'cases'/suffix/'recipe.json'
        contract = HERE/entry['measurement_contract']
        for candidate in ('primary', 'fallback1'):
            selected = entry if candidate == 'primary' else entry['candidates'][0]
            output = SCRATCH/'boundary-compat'/suffix/candidate
            receipt_path = output/'compatibility.json'
            valid = False
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_text())
                valid = (receipt.get('passed') is True and
                         receipt.get('construction_sha256') == selected['construction_sha256'] and
                         receipt.get('fixture_recipe_sha256') == sha(recipe) and
                         receipt.get('measurement_contract_sha256') == sha(contract) and
                         receipt.get('runtime_manifest_sha256') == manifest['runtime_manifest_sha256'])
            if not valid:
                if output.exists():
                    output = SCRATCH/'boundary-compat'/suffix/(candidate+'-retry')
                    receipt_path = output/'compatibility.json'
                output.parent.mkdir(parents=True, exist_ok=True)
                command = [str(ROOT/'.venv-cpu/bin/python'), str(ROOT/'runtime.py'),
                           'compatibility', '--manifest', str(MANIFEST),
                           '--case', entry['case_id'], '--candidate', candidate,
                           '--output', str(output), '--library', str(ROOT/'runtime/library'),
                           '--validator', str(SCRATCH/'decoder/.lake/build/bin/adapterCheck')]
                log = SCRATCH/'boundary-compat'/suffix/(candidate+'-command.log')
                with log.open('w') as stream:
                    result = subprocess.run(command, cwd=ROOT, env=environment,
                                            stdout=stream, stderr=subprocess.STDOUT)
                if result.returncode:
                    raise RuntimeError(f'{suffix}/{candidate} compatibility failed; see {log}')
                receipt = json.loads(receipt_path.read_text())
            target = HERE/'draft-boundary-proofs'/suffix/candidate
            target.mkdir(parents=True, exist_ok=True)
            for source, destination in (
                ('compatibility.json', 'receipt.json'),
                ('compatibility-analysis.log', 'analysis.log'),
                ('negative-analysis.log', 'negative.log'),
            ):
                shutil.copy2(output/source, target/destination)
            proof_rows.append({'case_id': entry['case_id'], 'candidate': candidate,
                               'construction_sha256': selected['construction_sha256'],
                               'fixture_sha256': receipt['fixture_sha256'],
                               'receipt': (target/'receipt.json').relative_to(HERE).as_posix(),
                               'receipt_sha256': sha(target/'receipt.json'),
                               'passed': receipt['passed'],
                               'physical_acceptance_claimed': False})
            print(json.dumps(proof_rows[-1], sort_keys=True), flush=True)
    summary = {'format': 'c179824-boundary-compatibility-proof-v1',
               'cases': proof_rows, 'all_passed': all(row['passed'] for row in proof_rows),
               'original_native_observed': False}
    (HERE/'draft-boundary-compatibility-receipt.json').write_text(
        json.dumps(summary, indent=2)+'\n')


if __name__ == '__main__':
    main()
