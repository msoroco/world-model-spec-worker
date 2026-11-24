"""Run active-runtime source-bound compatibility for the two device probes."""
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
    output = ROOT / '.runtime-work/c10389-v3-current-compat' / stem
    if output.exists():
        raise ValueError('Prior diagnostic attempt exists; retain it')
    returned = HERE / 'current-v3-compat-proof' / stem
    returned.mkdir(parents=True, exist_ok=True)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'compatibility', '--manifest', str(HERE / 'current-v3-draft-manifest.json'),
               '--case', HERE.name + '__' + args.suffix,
               '--candidate', args.candidate, '--output', str(output),
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
        raise ValueError(f'{stem} compatibility failed; see {log}')
    paths = {}
    for name in ('compatibility.json', 'compatibility-analysis.log',
                 'negative-analysis.log', 'analysis-report.json'):
        source = output / name
        returned_name = 'analysis.log' if name == 'compatibility-analysis.log' else name
        target = returned / returned_name
        target.write_text(source.read_text().rstrip() + '\n')
        paths[returned_name] = sha(target)
    summary = {'format': 'c10389-current-v3-compatibility-proof',
               'case_id': HERE.name + '__' + args.suffix,
               'candidate_id': args.candidate,
               'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
               'manifest_sha256': sha(HERE / 'current-v3-draft-manifest.json'),
               'command': ' '.join(command), 'exit_code': completed.returncode,
               'log_sha256': sha(log), 'files': paths,
               'native_executed': False, 'physical_acceptance_claimed': False}
    summary_path = returned / 'summary.json'
    summary_path.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'case': args.suffix, 'candidate': args.candidate,
                      'proof_sha256': sha(summary_path)}))


if __name__ == '__main__':
    main()
