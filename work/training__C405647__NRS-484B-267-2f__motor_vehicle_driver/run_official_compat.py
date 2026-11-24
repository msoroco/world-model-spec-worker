"""Exercise all selected official-vehicle candidates on the current runtime."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

from run_current_compat import run

HERE = Path(__file__).resolve().parent


def main():
    names = [('official_approach', candidate)
             for candidate in ('primary', 'fallback1', 'fallback2')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, names))
    report = {'format': 'c405647-2f-official-compatibility-matrix-v1',
              'results': results, 'all_passed': all(r['exit_code'] == 0 for r in results),
              'physical_acceptance': False}
    path = HERE / 'current-public/official-matrix.json'
    path.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'passed': report['all_passed'], 'results': len(results),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    if not report['all_passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
