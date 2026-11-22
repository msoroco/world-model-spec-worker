"""Run one exact candidate through the canonical selected CPU commands."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'
RUNTIME = ROOT / 'runtime.py'
LIBRARY = ROOT / 'runtime/pipeline/library'
VALIDATOR = ROOT / '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, log):
    result = subprocess.run([str(PYTHON), str(RUNTIME), *map(str, args)],
                            cwd=ROOT, capture_output=True, text=True)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout + result.stderr)
    if result.returncode:
        raise ValueError(f'Exact selected command failed ({result.returncode}): {log}: '
                         + (result.stderr or result.stdout)[-1200:])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('case', choices=('reference', 'contrast', 'divided_reference', 'divided_opening'))
    parser.add_argument('candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'))
    args = parser.parse_args()
    case_id = HERE.name + '__' + args.case
    base = ROOT / '.runtime-work/c111662-selected-current' / args.case / args.candidate
    returned = HERE / 'selected-current-chain' / args.case / args.candidate
    returned.mkdir(parents=True, exist_ok=True)
    common = ['--manifest', MANIFEST, '--case', case_id, '--candidate', args.candidate]
    command(['offline', *common, '--output', base / 'offline', '--python', PYTHON],
            returned / 'offline.log')
    command(['compatibility', *common, '--output', base / 'compatibility',
             '--library', LIBRARY, '--validator', VALIDATOR], returned / 'compatibility.log')
    compatibility = json.loads((base / 'compatibility/compatibility.json').read_text())
    if compatibility['passed'] is not True or compatibility['candidate_id'] != args.candidate:
        raise ValueError('Wrong selected compatibility receipt')
    command(['process-saved', '--manifest', MANIFEST, '--case', case_id,
             '--attempt', base / 'compatibility', '--output', base / 'saved',
             '--library', LIBRARY, '--validator', VALIDATOR], returned / 'saved.log')
    saved = json.loads((base / 'saved/v0001/processing.json').read_text())
    if not (saved['passed'] and saved['recorded_only'] and saved['originals_preserved']):
        raise ValueError('Selected saved processing failed')
    receipt = {'format': 'c111662-canonical-selected-cpu-chain-v1',
               'case_id': case_id, 'candidate_id': args.candidate,
               'canonical_manifest_sha256': sha(MANIFEST),
               'offline_log_sha256': sha(returned / 'offline.log'),
               'compatibility_log_sha256': sha(returned / 'compatibility.log'),
               'compatibility_receipt_sha256': sha(base / 'compatibility/compatibility.json'),
               'saved_log_sha256': sha(returned / 'saved.log'),
               'saved_receipt_sha256': sha(base / 'saved/v0001/processing.json'),
               'passed': True, 'synthetic_cpu_only': True,
               'original_native_observed': False, 'physical_or_legal_acceptance_claimed': False}
    (returned / 'proof.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    for path in returned.iterdir():
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Oversized returned file: ' + str(path))
    print(json.dumps({'case': args.case, 'candidate': args.candidate,
                      'proof_sha256': sha(returned / 'proof.json')}))


if __name__ == '__main__':
    main()
