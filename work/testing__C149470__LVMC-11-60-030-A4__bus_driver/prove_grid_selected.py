"""Bind 13 current-hash selected primary/fallback, physical and audit receipts."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

from bus_curb import CASES
import build_selected_draft
import build_fallback_draft
import prove_physical_diagnostic

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'
DECODER = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(value):
    MANIFEST.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def command(args, log, expected=0):
    with (HERE / log).open('w', encoding='utf-8') as output:
        result = subprocess.run(args, cwd=ROOT, env=os.environ.copy(),
                                stdout=output, stderr=subprocess.STDOUT, check=False)
    if result.returncode != expected:
        raise RuntimeError(f'{log}: expected {expected}, got {result.returncode}')
    return ' '.join(args)


def reuse_or_run(args, log, marker, required):
    path = HERE / log
    if (path.is_file() and marker in path.read_text()
            and all(Path(item).is_file() for item in required)):
        return ' '.join(args)
    return command(args, log)


def prove_case(case):
    name = case.name
    cid = HERE.name + '__' + name
    base = [str(PYTHON), 'runtime.py']
    selected_output = ROOT / '.runtime-work/c149470' / ('grid10-selected-offline-' + name)
    fallback_output = ROOT / '.runtime-work/c149470' / ('grid10-fallback-offline-' + name)
    compatibility_output = ROOT / '.runtime-work/c149470' / ('grid10-fallback-compat-' + name)
    primary_args = base + ['offline', '--manifest', str(MANIFEST), '--case', cid,
                           '--output', str(selected_output), '--python', str(PYTHON)]
    fallback_args = base + ['offline', '--manifest', str(MANIFEST), '--case', cid,
                            '--candidate', 'fallback1', '--output', str(fallback_output),
                            '--python', str(PYTHON)]
    compatibility_args = base + ['compatibility', '--manifest', str(MANIFEST),
                                 '--case', cid, '--candidate', 'fallback1',
                                 '--output', str(compatibility_output),
                                 '--library', 'runtime/library', '--validator', str(DECODER)]
    primary_log = 'cpu-grid-selected-offline-' + name + '.log'
    fallback_log = 'cpu-grid-fallback-offline-' + name + '.log'
    compatibility_log = 'cpu-grid-fallback-compat-' + name + '.log'
    primary_cmd = reuse_or_run(primary_args, primary_log, '"offline_passed": true',
                               [selected_output / 'offline.log'])
    fallback_cmd = reuse_or_run(fallback_args, fallback_log, '"offline_passed": true',
                                [fallback_output / 'offline.log'])
    reuse_or_run(compatibility_args, compatibility_log, '"passed": true',
                 [compatibility_output / name for name in
                  ('compatibility.json', 'compatibility-analysis.log', 'negative-analysis.log')])
    proof_dir = HERE / 'proofs' / ('fallback1-' + name)
    proof_dir.mkdir(parents=True, exist_ok=True)
    for source, target in (('compatibility.json', 'receipt.json'),
                           ('compatibility-analysis.log', 'analysis.log'),
                           ('negative-analysis.log', 'negative.log')):
        shutil.copyfile(compatibility_output / source, proof_dir / target)
    print('selected/fallback offline and fallback compatibility:', name, flush=True)
    return name, {'primary': (primary_cmd, primary_log),
                  'fallback': (fallback_cmd, fallback_log),
                  'proof_dir': proof_dir}


def main():
    build_selected_draft.main()
    build_fallback_draft.main()
    with ThreadPoolExecutor(max_workers=3) as pool:
        proofs = dict(pool.map(prove_case, CASES))
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        name = entry['case_id'].removeprefix(HERE.name + '__')
        proof = proofs[name]
        primary_cmd, primary_log = proof['primary']
        entry['offline'] = {'construction_sha256': entry['construction_sha256'],
                            'command': primary_cmd, 'exit_code': 0,
                            'log': primary_log, 'log_sha256': sha(HERE / primary_log)}
        candidate = entry['candidates'][0]
        fallback_cmd, fallback_log = proof['fallback']
        candidate['offline'] = {'construction_sha256': candidate['construction_sha256'],
                                'command': fallback_cmd, 'exit_code': 0,
                                'log': fallback_log, 'log_sha256': sha(HERE / fallback_log)}
        folder = proof['proof_dir']
        candidate['compatibility'] = {
            'receipt': str((folder / 'receipt.json').relative_to(HERE)),
            'sha256': sha(folder / 'receipt.json'),
            'log': str((folder / 'analysis.log').relative_to(HERE)),
            'negative_log': str((folder / 'negative.log').relative_to(HERE))}
    write(manifest)
    prove_physical_diagnostic.main()
    manifest = json.loads(MANIFEST.read_text())
    delivery_script = HERE / 'prove_original_delivery.py'
    for entry in manifest['cases']:
        cid = entry['case_id']
        name = cid.removeprefix(HERE.name + '__')
        base = [str(PYTHON), str(delivery_script), '--case', cid]
        positive_log = 'cpu-grid-delivery-positive-' + name + '.log'
        negative_log = 'cpu-grid-delivery-negative-' + name + '.log'
        positive_cmd = command(base, positive_log)
        negative_cmd = command(base + ['--negative-missing-review'], negative_log, 2)
        if 'original reviewed bus site packet missing' not in (HERE / negative_log).read_text():
            raise ValueError('missing original source negative did not reject')
        entry['delivery_acceptance'] = {
            'case_id': cid, 'sets': ['full-test'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'cpu_proof_kind': 'mock_only_contract_wiring',
            'script': delivery_script.name, 'script_sha256': sha(delivery_script),
            'command': positive_cmd, 'test_exit_code': 0,
            'test_log': positive_log, 'test_log_sha256': sha(HERE / positive_log),
            'negative_command': negative_cmd, 'negative_exit_code': 2,
            'negative_expected_error': 'original reviewed bus site packet missing',
            'negative_log': negative_log, 'negative_log_sha256': sha(HERE / negative_log)}
    write(manifest)
    print('selected package proofs:', len(manifest['cases']))


if __name__ == '__main__':
    main()
