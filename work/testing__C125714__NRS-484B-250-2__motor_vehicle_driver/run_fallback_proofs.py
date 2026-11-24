"""Run pinned offline and diagnostic compatibility for exact fallback1 cases."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--validator', type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    folder = Path(__file__).resolve().parent
    scratch = args.scratch.resolve()
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'output'),
               TMPDIR=str(scratch / 'tmp'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        candidate = entry['candidates'][0]
        case_dir = folder / 'cases' / suffix
        offline_output = scratch / ('offline-fallback1-' + suffix)
        offline_cmd = [sys.executable, 'runtime.py', 'offline', '--manifest',
                       str(manifest_path), '--case', entry['case_id'],
                       '--candidate', 'fallback1', '--output', str(offline_output)]
        if not (offline_output / 'offline.log').is_file():
            proc = subprocess.run(offline_cmd, capture_output=True, text=True, env=env)
            if proc.returncode:
                raise RuntimeError(suffix + ' offline: ' + proc.stdout + proc.stderr)
        offline_log = case_dir / 'fallback1-offline.log'
        shutil.copyfile(offline_output / 'offline.log', offline_log)
        candidate['offline'] = {'command': ' '.join(offline_cmd),
                                'construction_sha256': candidate['construction_sha256'],
                                'exit_code': 0,
                                'log': str(offline_log.relative_to(folder)),
                                'log_sha256': sha(offline_log)}
        compat_output = scratch / ('compat-fallback1-' + suffix)
        compat_cmd = [sys.executable, 'runtime.py', 'compatibility', '--manifest',
                      str(manifest_path), '--case', entry['case_id'],
                      '--candidate', 'fallback1', '--output', str(compat_output),
                      '--library', 'runtime/library', '--validator', str(args.validator)]
        if not (compat_output / 'compatibility.json').is_file():
            proc = subprocess.run(compat_cmd, capture_output=True, text=True, env=env)
            if proc.returncode:
                raise RuntimeError(suffix + ' compatibility: ' + proc.stdout + proc.stderr)
        copied = {}
        for source_name, target_name in (('compatibility-analysis.log','fallback1-analysis.log'),
                                         ('negative-analysis.log','fallback1-negative.log')):
            source = compat_output / source_name
            target = case_dir / target_name
            content = source.read_text().rstrip() + '\n' if source.stat().st_size else ''
            target.write_text(content)
            copied[source_name] = target
        receipt = json.loads((compat_output / 'compatibility.json').read_text())
        receipt['log_sha256'] = sha(copied['compatibility-analysis.log'])
        receipt['negative_log_sha256'] = sha(copied['negative-analysis.log'])
        receipt_path = case_dir / 'fallback1-compatibility.json'
        receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        candidate['compatibility'] = {'command': ' '.join(compat_cmd),
                                      'receipt': str(receipt_path.relative_to(folder)),
                                      'sha256': sha(receipt_path),
                                      'log': str(copied['compatibility-analysis.log'].relative_to(folder)),
                                      'negative_log': str(copied['negative-analysis.log'].relative_to(folder))}
        print(suffix, 'fallback1 offline and compatibility passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
