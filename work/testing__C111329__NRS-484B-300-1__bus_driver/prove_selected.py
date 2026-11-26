"""Bind current-hash offline, compatibility, saved and physical receipts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor

from package_spec import CASES, HERE, ROOT, case_id

PYTHON = ROOT / '.venv-cpu/bin/python'
DECODER = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
MANIFEST = HERE / 'execution-manifest.json'
SCRATCH = ROOT / '.runtime-work/c111329/proof-v3'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(args, log):
    with log.open('w') as handle:
        result = subprocess.run(args, cwd=ROOT, env=os.environ.copy(),
                                stdout=handle, stderr=subprocess.STDOUT, check=False)
    if result.returncode:
        raise RuntimeError(f'{log}: exit {result.returncode}')
    return ' '.join(str(arg) for arg in args)


def prove(pair):
    name, candidate = pair
    cid = case_id(name)
    tag = name + ('-fallback1' if candidate else '')
    args = [str(PYTHON), 'runtime.py']
    select = ['--candidate', 'fallback1'] if candidate else []
    offline = SCRATCH / ('offline-' + tag)
    compat = SCRATCH / ('compat-' + tag)
    saved = SCRATCH / ('saved-' + tag)
    offline_log = HERE / ('cpu-offline-' + tag + '.log')
    offline_command = run(args + ['offline', '--manifest', str(MANIFEST),
                                  '--case', cid] + select + ['--output', str(offline),
                                  '--python', str(PYTHON)], offline_log)
    compat_log = HERE / ('cpu-compat-' + tag + '.log')
    run(args + ['compatibility', '--manifest', str(MANIFEST), '--case', cid] +
        select + ['--output', str(compat), '--library', 'runtime/library',
                  '--validator', str(DECODER)], compat_log)
    saved_log = HERE / ('cpu-saved-' + tag + '.log')
    saved_command = run(args + ['process-saved', '--manifest', str(MANIFEST), '--case', cid,
                                '--attempt', str(compat), '--output', str(saved),
                                '--library', 'runtime/library', '--validator', str(DECODER)],
                        saved_log)
    proof = HERE / 'proofs' / tag
    proof.mkdir(parents=True, exist_ok=True)
    for source, target in (('compatibility.json', 'receipt.json'),
                           ('compatibility-analysis.log', 'analysis.log'),
                           ('negative-analysis.log', 'negative.log')):
        shutil.copyfile(compat / source, proof / target)
    print('offline, compatibility, saved:', tag, flush=True)
    return tag, {'offline': {'construction_sha256': sha(HERE / 'cases' / name /
                                ('fallback1/construction.json' if candidate else 'construction.json')),
                            'command': offline_command, 'exit_code': 0,
                            'log': offline_log.name, 'log_sha256': sha(offline_log)},
                 'compatibility': {'receipt': str((proof / 'receipt.json').relative_to(HERE)),
                                   'sha256': sha(proof / 'receipt.json'),
                                   'log': str((proof / 'analysis.log').relative_to(HERE)),
                                   'negative_log': str((proof / 'negative.log').relative_to(HERE))},
                 'saved': {'command': saved_command,
                           'exit_code': 0, 'log': saved_log.name,
                           'log_sha256': sha(saved_log)}}


def main():
    if not DECODER.is_file():
        raise FileNotFoundError(DECODER)
    rows = [(name, candidate) for name, *_ in CASES for candidate in (False, True)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        proofs = dict(pool.map(prove, rows))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(HERE.name + '__')
        primary, fallback = proofs[name], proofs[name + '-fallback1']
        entry['offline'] = primary['offline']
        entry['compatibility'] = primary['compatibility']
        entry['negative'] = {'log': primary['compatibility']['negative_log']}
        entry['saved_diagnostic'] = primary['saved']
        entry['candidates'][0]['offline'] = fallback['offline']
        entry['candidates'][0]['compatibility'] = fallback['compatibility']
        entry['candidates'][0]['saved_diagnostic'] = fallback['saved']
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
