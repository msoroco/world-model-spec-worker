"""Run all four current-hash offline, compatibility and saved-only proofs."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.selected-draft.json'
SCRATCH = ROOT / '.runtime-work/c229628-selected-v6'
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    return '\n'.join(line.rstrip() for line in text.splitlines()).rstrip() + '\n' if text.strip() else ''


def execute(command, log):
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(clean(result.stdout))
    if result.returncode:
        raise ValueError('selected CPU proof failed: ' + log.name)
    return json.loads(result.stdout)


def run():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if not VALIDATOR.is_file():
        raise ValueError('pinned Lean validator executable missing')
    manifest = json.loads(MANIFEST.read_text())
    if len(manifest['cases']) != 4:
        raise ValueError('four exact aid cases required')
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(HERE.name + '__')
        offline = SCRATCH / 'offline' / suffix
        compatible = SCRATCH / 'compatible' / suffix
        saved = SCRATCH / 'saved' / suffix
        if offline.exists() or compatible.exists() or saved.exists():
            raise ValueError('retain prior proof; use fresh scratch version')
        command = [sys.executable, str(ROOT / 'runtime.py'), 'offline',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--output', str(offline), '--python', sys.executable]
        output = HERE / ('proof-selected-offline-' + suffix + '.log')
        receipt = execute(command, output)
        if receipt.get('offline_passed') is not True or receipt.get('simulation_started') is not False:
            raise ValueError('offline did not stay CPU only')
        entry['offline'] = {'command': ' '.join(command), 'exit_code': 0,
                            'log': output.name, 'log_sha256': sha(output),
                            'construction_sha256': entry['construction_sha256']}
        command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--output', str(compatible), '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        execute(command, HERE / ('proof-compat-command-' + suffix + '.log'))
        for source, target in [('compatibility.json', 'proof-compat-receipt-' + suffix + '.json'),
                               ('compatibility-analysis.log', 'proof-compat-analysis-' + suffix + '.log'),
                               ('negative-analysis.log', 'proof-compat-negative-' + suffix + '.log')]:
            (HERE / target).write_text(clean((compatible / source).read_text()))
        command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                   '--manifest', str(MANIFEST), '--case', entry['case_id'],
                   '--attempt', str(compatible), '--output', str(saved),
                   '--library', str(ROOT / 'runtime/library'),
                   '--validator', str(VALIDATOR)]
        receipt = execute(command, HERE / ('proof-selected-saved-' + suffix + '.log'))
        if not (receipt.get('passed') is True and receipt.get('recorded_only') is True and
                receipt.get('originals_preserved') is True):
            raise ValueError('saved replay did not preserve originals')
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print('current-hash selected aid proofs:', run())
