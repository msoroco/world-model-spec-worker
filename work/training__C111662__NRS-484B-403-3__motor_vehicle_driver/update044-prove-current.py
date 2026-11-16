"""Run migrated-input offline, compatibility, and saved CPU proofs per candidate."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def run(name, args, log):
    with log.open('w') as stream:
        completed = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                                   timeout=1200, check=False)
    if completed.returncode:
        raise RuntimeError(f'{name} failed ({completed.returncode}): {log}')


def main(case, candidate):
    if case not in CASES or candidate not in CANDIDATES:
        raise ValueError('Unknown selected case or candidate')
    proof = HERE / 'update044-current-proof' / case / candidate
    proof.mkdir(parents=True, exist_ok=True)
    output = ROOT / '.runtime-work' / 'update044-c111662' / case / candidate
    manifest = HERE / 'execution-manifest.json'
    case_id = AID + '__' + case
    py = sys.executable
    run('offline', [py, 'runtime.py', 'offline', '--manifest', str(manifest),
                    '--case', case_id, '--candidate', candidate,
                    '--output', str(output / 'offline'), '--python', py], proof / 'offline.log')
    run('fixture', [py, str(HERE / 'update043-generate-current-fixture.py'),
                    '--case', case, '--candidate', candidate,
                    '--offline', str(output / 'offline')], proof / 'fixture.log')
    mini = HERE / f'update043-current-manifest-{case}-{candidate}.json'
    common = ['--manifest', str(mini), '--case', case_id, '--candidate', candidate,
              '--library', 'runtime/pipeline/library',
              '--validator', '.runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck']
    run('compatibility', [py, 'runtime.py', 'compatibility', *common,
                          '--output', str(output / 'compat')], proof / 'compat.log')
    run('process-saved', [py, 'runtime.py', 'process-saved', *common,
                          '--attempt', str(output / 'compat'),
                          '--output', str(output / 'saved')], proof / 'saved.log')
    for name, path in [('compatibility', output / 'compat' / 'compatibility.json'),
                       ('processing', output / 'saved' / 'processing.json')]:
        if path.exists():
            (proof / f'{name}.json').write_bytes(path.read_bytes())
    print(json.dumps({'case': case, 'candidate': candidate, 'passed': True,
                      'proof': str(proof.relative_to(ROOT))}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=CANDIDATES, required=True)
    args = parser.parse_args()
    main(args.case, args.candidate)
