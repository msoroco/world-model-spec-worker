"""Reprove forty current same-cell draft candidates after fixed-flagger binding."""
import concurrent.futures
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-combined-capture-manifest.json'
OUTPUT = ROOT / '.runtime-work/c183370-update125-combined-offline-matrix'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(item):
    case, candidate, construction_sha = item
    destination = OUTPUT / case.rsplit('__', 1)[-1] / candidate
    cmd = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
           'offline', '--manifest', str(MANIFEST), '--case', case,
           '--candidate', candidate, '--output', str(destination)]
    run = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    log = destination / 'command.log'
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(run.stdout + run.stderr)
    selection_path = destination / 'candidate-selection.json'
    selection = json.loads(selection_path.read_text()) if selection_path.exists() else {}
    passed = (run.returncode == 0 and selection.get('case_id') == case and
              selection.get('candidate_id') == candidate and
              selection.get('manifest_sha256') == sha(MANIFEST) and
              selection.get('construction_sha256') == construction_sha)
    return {'case_id': case, 'candidate_id': candidate, 'passed': passed,
            'returncode': run.returncode, 'construction_sha256': construction_sha,
            'selection_sha256': sha(selection_path) if selection_path.exists() else None,
            'log_sha256': sha(log), 'log': str(log.relative_to(ROOT))}


def main():
    manifest = json.loads(MANIFEST.read_text())
    items = []
    for entry in manifest['cases']:
        items.append((entry['case_id'], 'primary', entry['construction_sha256']))
        items.extend((entry['case_id'], candidate['id'], candidate['construction_sha256'])
                     for candidate in entry['candidates'])
    assert len(items) == 40 and len(set((a, b) for a, b, _ in items)) == 40
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(prove, items))
    result = {'manifest_sha256': sha(MANIFEST), 'cases': 10,
              'candidates': len(rows), 'passed': sum(row['passed'] for row in rows),
              'results': rows}
    path = HERE / 'update125-combined-offline-matrix.json'
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidates': len(rows), 'passed': result['passed'],
                      'report_sha256': sha(path)}, sort_keys=True))
    if result['passed'] != len(rows):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
