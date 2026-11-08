"""Run all eight exact unselected park-case bundles through pinned offline CLI."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-park-execution-manifest.json'
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    env = dict(os.environ)
    env['LD_LIBRARY_PATH'] = str(ROOT / '.runtime-work/geos-wheel/shapely.libs') + os.pathsep + env.get('LD_LIBRARY_PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10052-park-cases-offline-'))
    receipts = []
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for name in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = entry if name == 'primary' else next(c for c in entry['candidates'] if c['id'] == name)
            output = scratch / (suffix + '-' + name)
            command = [str(PYTHON), str(ROOT / 'runtime.py'), 'offline',
                       '--manifest', str(MANIFEST), '--case', entry['case_id'],
                       '--candidate', name, '--output', str(output), '--python', str(PYTHON)]
            result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    timeout=300)
            log_path = HERE / 'draft-park-cases' / suffix / name / 'command.log'
            log_path.write_text(result.stdout)
            unit_path = output / 'offline.log'
            receipt = {'case_id': entry['case_id'], 'candidate': name,
                       'exit_code': result.returncode,
                       'construction_sha256': ref['construction_sha256'],
                       'command_log': log_path.relative_to(HERE).as_posix(),
                       'command_log_sha256': sha(log_path),
                       'unit_log': unit_path.relative_to(ROOT).as_posix() if unit_path.is_file() else None,
                       'unit_log_sha256': sha(unit_path) if unit_path.is_file() else None,
                       'selected': False}
            receipts.append(receipt)
            print(suffix, name, 'exit', result.returncode, flush=True)
    summary = {'format': 'c10052-distinct-park-offline-v1',
               'manifest_sha256': sha(MANIFEST), 'results': receipts,
               'passed': all(r['exit_code'] == 0 for r in receipts),
               'selected': False}
    (HERE / 'park-case-offline-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    if not summary['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
