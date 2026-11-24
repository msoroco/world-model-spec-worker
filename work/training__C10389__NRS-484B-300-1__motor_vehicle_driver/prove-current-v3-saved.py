"""Exercise recorded-only processing from a frozen synthetic CPU attempt."""
import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('probe_1', 'probe_2'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2'), required=True)
    args = parser.parse_args()
    stem = f'{args.suffix}-{args.candidate}'
    attempt = ROOT / '.runtime-work/c10389-v3-current-compat' / stem
    if stem == 'probe_1-fallback1':
        attempt = ROOT / '.runtime-work/c10389-v3-draft-p1-f1-compat'
    if not (attempt / 'compatibility.json').is_file():
        raise ValueError('Source-bound compatibility attempt missing: ' + stem)
    output = ROOT / '.runtime-work/c10389-v3-current-saved' / stem
    if output.exists():
        raise ValueError('Retain prior saved diagnostic attempt: ' + stem)
    returned = HERE / 'current-v3-saved-proof' / stem
    returned.mkdir(parents=True, exist_ok=True)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(HERE / 'current-v3-draft-manifest.json'),
               '--case', HERE.name + '__' + args.suffix,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(ROOT / 'runtime/library'),
               '--validator', str(ROOT / '.runtime-work/c10389-active-decoder/.lake/build/bin/adapterCheck')]
    env = dict(os.environ)
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['MPLCONFIGDIR'] = str(ROOT / '.runtime-work/mplconfig')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    completed = subprocess.run(command, capture_output=True, text=True, env=env)
    log = returned / 'command.log'
    log.write_text((completed.stdout + completed.stderr).rstrip() + '\n')
    if completed.returncode:
        raise ValueError(f'{stem} saved processing failed; see {log}')
    version = output / 'v0001'
    paths = {}
    for name in ('processing.json', 'analysis.log'):
        source = version / name
        target = returned / name
        target.write_text(source.read_text().rstrip() + '\n')
        paths[name] = sha(target)
    processing = json.loads((version / 'processing.json').read_text())
    if not processing['recorded_only'] or not processing['originals_preserved'] or processing['missing_evidence']:
        raise ValueError('Saved processing did not preserve complete source analysis')
    summary = {'format': 'c10389-current-v3-saved-proof',
               'case_id': HERE.name + '__' + args.suffix,
               'candidate_id': args.candidate,
               'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
               'manifest_sha256': sha(HERE / 'current-v3-draft-manifest.json'),
               'command': ' '.join(command), 'exit_code': completed.returncode,
               'log_sha256': sha(log), 'files': paths,
               'source_preserved': True, 'recorded_only': True,
               'physical_acceptance_claimed': False}
    summary_path = returned / 'summary.json'
    summary_path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'case': args.suffix, 'candidate': args.candidate,
                      'proof_sha256': sha(summary_path)}))


if __name__ == '__main__':
    main()
