"""Reprove every selected primary and fallback against the current runtime."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c10052-disposition-compat-all'
FIRST = REPO / '.runtime-work/c10052-disposition-compat/rider_bicycle_clear-primary'
PYTHON = REPO / '.venv-cpu/bin/python'
DECODER = REPO / '.runtime-work/c10052-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean(path):
    content = path.read_text()
    if (not content.endswith('\n') or content.endswith('\n\n')
            or any(line != line.rstrip() for line in content.splitlines())):
        raise ValueError('Returned proof log needs whitespace cleanup: ' + str(path))


def prove(case, candidate):
    suffix = case['case_id'].rsplit('__', 1)[-1]
    ident = candidate.get('id', 'primary')
    selected = ROOT / Path(candidate['construction']).parts[0]
    target = selected if ident == 'primary' else selected / (ident + '-proof')
    receipt_target = target / ('compatibility.json' if ident == 'primary' else 'receipt.json')
    log_target = target / ('analysis.log' if ident == 'primary' else 'analysis.log')
    negative_target = target / ('negative.log' if ident == 'primary' else 'negative.log')
    prior = candidate.get('compatibility', {})
    if receipt_target.is_file() and prior.get('sha256') == sha(receipt_target):
        receipt = json.loads(receipt_target.read_text())
        if (receipt.get('construction_sha256') == candidate['construction_sha256']
                and receipt.get('measurement_contract_sha256') == sha(ROOT / case['measurement_contract'])
                and receipt.get('log_sha256') == sha(log_target)
                and receipt.get('negative_log_sha256') == sha(negative_target)):
            return suffix, ident, 'retained', prior
    output = FIRST if suffix == 'rider_bicycle_clear' and ident == 'primary' else SCRATCH / f'{suffix}-{ident}'
    if output != FIRST:
        if output.exists():
            shutil.rmtree(output)
        command = [str(PYTHON), 'runtime.py', 'compatibility', '--manifest',
                   str(MANIFEST.relative_to(REPO)), '--case', case['case_id'],
                   '--output', str(output), '--library', 'runtime/library',
                   '--validator', str(DECODER)]
        if ident != 'primary':
            command += ['--candidate', ident]
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH)
        env['TMPDIR'] = str(SCRATCH)
        run = subprocess.run(command, cwd=REPO, env=env, text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        if run.returncode:
            raise RuntimeError(f'{suffix}/{ident} compatibility failed: {run.stdout[-1400:]}')
    receipt_source = output / 'compatibility.json'
    proof = json.loads(receipt_source.read_text())
    assert proof['passed'] and proof['construction_sha256'] == candidate['construction_sha256']
    assert proof['measurement_contract_sha256'] == sha(ROOT / case['measurement_contract'])
    for source_name, destination in [('compatibility-analysis.log', log_target),
                                      ('negative-analysis.log', negative_target),
                                      ('compatibility.json', receipt_target)]:
        source = output / source_name
        if source.suffix == '.log':
            clean(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
    assert proof['log_sha256'] == sha(log_target)
    assert proof['negative_log_sha256'] == sha(negative_target)
    if output != FIRST:
        shutil.rmtree(output)
    spec = {'receipt': str(receipt_target.relative_to(ROOT)),
            'sha256': sha(receipt_target),
            'log': str(log_target.relative_to(ROOT)),
            'negative_log': str(negative_target.relative_to(ROOT))}
    return suffix, ident, 'proved', spec


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not DECODER.is_file():
        raise FileNotFoundError(DECODER)
    manifest = json.loads(MANIFEST.read_text())
    jobs = [(case, candidate) for case in manifest['cases']
            for candidate in [case] + case['candidates']]
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {executor.submit(prove, case, candidate): (case, candidate)
                   for case, candidate in jobs}
        for future in as_completed(futures):
            case, candidate = futures[future]
            suffix, ident, state, spec = future.result()
            candidate['compatibility'] = spec
            if ident == 'primary':
                case['negative'] = {'log': spec['negative_log']}
            MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
            print(suffix, ident, state, flush=True)


if __name__ == '__main__':
    main()
