"""Run and bind C405341 exact-case synthetic compatibility CPU proofs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from emergency_construction import CASES
from native_packet import AID as ASSIGNMENT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work' / 'c405341'
VALIDATOR = ROOT / '.runtime-work/c233829/decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_one(case, candidate=None):
    name = case.suffix
    case_id = ASSIGNMENT + '__' + name
    label = name + ('-fallback1' if candidate else '')
    output = SCRATCH / ('compat-' + label + '-v3')
    if (output / 'compatibility.json').is_file():
        result = json.loads((output / 'compatibility.json').read_text())
        if result.get('case_id') == case_id and result.get('passed') is True:
            return name, output, 0
    if output.exists():
        raise ValueError('retain failed compatibility attempt; choose a new output: ' + name)
    command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
        '--manifest', str(HERE / 'execution-manifest.json'), '--case', case_id,
        '--output', str(output), '--library', str(ROOT / 'runtime/library'),
        '--validator', str(VALIDATOR)]
    if candidate:
        command += ['--candidate', candidate]
    environment = dict(os.environ)
    environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(SCRATCH / 'output-root')
    environment['TMPDIR'] = str(SCRATCH / 'tmp')
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    result = subprocess.run(command, cwd=ROOT, env=environment,
                            capture_output=True, text=True, timeout=1200)
    (SCRATCH / ('compat-' + label + '-cli.log')).write_text(
        (result.stdout + result.stderr).rstrip() + '\n', encoding='utf-8')
    return label, output, result.returncode


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    (SCRATCH / 'output-root').mkdir(exist_ok=True)
    (SCRATCH / 'tmp').mkdir(exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError('pinned CPU Lean validator missing')
    outcomes = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(run_one, case, candidate)
                   for case in CASES for candidate in (None,)]
        for future in as_completed(futures):
            name, output, code = future.result()
            print(name, 'passed' if code == 0 else 'failed', flush=True)
            outcomes.append((name, output, code))
    if any(code for _, _, code in outcomes):
        raise ValueError('exact compatibility failures: ' + ', '.join(name for name, _, code in outcomes if code))
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    for name, output, _ in outcomes:
        suffix = name.removesuffix('-fallback1')
        candidate = name.endswith('-fallback1')
        case_id = ASSIGNMENT + '__' + suffix
        proof = json.loads((output / 'compatibility.json').read_text())
        if (proof.get('case_id') != case_id or not proof.get('passed') or
            proof.get('construction_sha256') != (entries[case_id]['candidates'][0]['construction_sha256']
                if candidate else entries[case_id]['construction_sha256'])):
            raise ValueError('compatibility receipt stale: ' + name)
        local_receipt = HERE / ('cpu-compat-' + name + '-receipt.json')
        local_analysis = HERE / ('cpu-compat-analysis-' + name + '.log')
        local_negative = HERE / ('cpu-compat-negative-' + name + '.log')
        shutil.copyfile(output / 'compatibility-analysis.log', local_analysis)
        shutil.copyfile(output / 'negative-analysis.log', local_negative)
        shutil.copyfile(output / 'compatibility.json', local_receipt)
        if sha(local_analysis) != proof['log_sha256'] or sha(local_negative) != proof['negative_log_sha256']:
            raise ValueError('compatibility logs changed: ' + name)
        entry = entries[case_id]
        if candidate:
            entry['candidates'][0]['compatibility'] = {
                'receipt': local_receipt.name, 'sha256': sha(local_receipt),
                'log': local_analysis.name, 'negative_log': local_negative.name}
        else:
            entry['compatibility'] = {'receipt': local_receipt.name,
                                      'sha256': sha(local_receipt),
                                      'log': local_analysis.name}
            entry['negative'] = {'log': local_negative.name}
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
