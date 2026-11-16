"""Run current public compatibility CLI for every unselected exact bundle."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    results = []
    for suffix in ('controlled_1', 'controlled_2'):
        case = HERE.name + '__' + suffix
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            output = ROOT / '.runtime-work' / ('c10316-public-' + suffix + '-' + candidate + '-' + sha(MANIFEST)[:10])
            log = HERE / ('public-compatibility-' + suffix + '-' + candidate + '.log')
            command = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                       '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
                       '--output', str(output), '--library', str(ROOT / 'runtime/pipeline/library'),
                       '--validator', str(VALIDATOR)]
            with log.open('w') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=300)
            receipt = output / 'compatibility.json'
            results.append({'case_id': case, 'candidate': candidate, 'exit_code': result.returncode,
                            'log': log.name, 'log_sha256': sha(log),
                            'receipt': str(receipt.relative_to(ROOT)) if receipt.exists() else None,
                            'receipt_sha256': sha(receipt) if receipt.exists() else None})
            print(suffix, candidate, result.returncode, flush=True)
    (HERE / 'public-compatibility-summary.json').write_text(json.dumps({
        'format': 'c10316-unselected-public-compatibility-summary', 'results': results,
        'selected_cases': 0, 'physical_acceptance_claimed': False}, indent=2) + '\n')
    if any(row['exit_code'] for row in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
