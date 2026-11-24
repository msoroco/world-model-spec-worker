"""Re-run all selected candidate compatibility proofs on current pinned runtime."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--validator', type=Path, required=True)
    parser.add_argument('--tag', default='rebind')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parent
    scratch = args.scratch.resolve()
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    manifest['runtime_manifest_sha256'] = sha(Path('runtime/SOURCE-MANIFEST.json'))
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(scratch / 'output'),
               TMPDIR=str(scratch / 'tmp'))
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        for candidate_id, target in [('primary', entry),
                                     ('fallback1', entry['candidates'][0])]:
            output = scratch / (args.tag + '-compat-' + candidate_id + '-' + suffix)
            command = [sys.executable, 'runtime.py', 'compatibility',
                       '--manifest', str(manifest_path), '--case', entry['case_id'],
                       '--candidate', candidate_id, '--output', str(output),
                       '--library', 'runtime/library', '--validator', str(args.validator)]
            proc = subprocess.run(command, capture_output=True, text=True, env=env)
            if proc.returncode:
                raise RuntimeError(suffix + ' ' + candidate_id + ': ' + proc.stdout + proc.stderr)
            case_dir = folder / 'cases' / suffix
            prefix = 'primary' if candidate_id == 'primary' else 'fallback1'
            analysis = case_dir / (prefix + '-compatibility-analysis.log' if candidate_id == 'primary'
                                   else prefix + '-analysis.log')
            negative = case_dir / (prefix + '-negative-analysis.log' if candidate_id == 'primary'
                                   else prefix + '-negative.log')
            for name, destination in [('compatibility-analysis.log', analysis),
                                      ('negative-analysis.log', negative)]:
                raw = (output / name).read_text()
                destination.write_text(raw.rstrip() + '\n' if raw else '')
            receipt = json.loads((output / 'compatibility.json').read_text())
            receipt['log_sha256'] = sha(analysis)
            receipt['negative_log_sha256'] = sha(negative)
            receipt_path = case_dir / (prefix + '-compatibility.json')
            receipt_path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
            target['compatibility'] = {'command': ' '.join(command),
                                       'receipt': str(receipt_path.relative_to(folder)),
                                       'sha256': sha(receipt_path),
                                       'log': str(analysis.relative_to(folder)),
                                       'negative_log': str(negative.relative_to(folder))}
            print(suffix, candidate_id, 'current-runtime compatibility passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
