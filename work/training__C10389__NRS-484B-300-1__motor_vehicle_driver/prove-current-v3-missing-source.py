"""Check recorded-only feedback when the required actor source is absent."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('probe_1', 'probe_2'), required=True)
    args = parser.parse_args()
    stem = args.suffix + '-primary'
    positive = ROOT / '.runtime-work/c10389-v3-current-compat' / stem
    negative = ROOT / '.runtime-work/c10389-v3-missing-source' / stem
    if negative.exists():
        raise ValueError('Retain prior missing-source diagnostic')
    shutil.copytree(positive, negative)
    (negative / 'native-raw-actors.jsonl').unlink()
    output = ROOT / '.runtime-work/c10389-v3-missing-source-saved' / stem
    returned = HERE / 'current-v3-missing-source-proof' / stem
    returned.mkdir(parents=True, exist_ok=True)
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(HERE / 'current-v3-draft-manifest.json'),
               '--case', HERE.name + '__' + args.suffix,
               '--attempt', str(negative), '--output', str(output),
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
        raise ValueError(f'{args.suffix} missing-source processing failed; see {log}')
    version = output / 'v0001'
    paths = {}
    for name in ('processing.json', 'feedback.json', 'analysis.log'):
        path = version / name
        target = returned / name
        target.write_text(path.read_text().rstrip() + '\n')
        paths[name] = sha(target)
    processing = json.loads((version / 'processing.json').read_text())
    feedback = json.loads((version / 'feedback.json').read_text())
    if (not processing['recorded_only'] or not processing['originals_preserved']
            or not processing['missing_evidence']
            or feedback['classification'] != 'incomplete_or_unavailable_law_evidence'
            or feedback['native_replay_requested']):
        raise ValueError('Missing source failed without actionable recorded-only feedback')
    summary = {'format': 'c10389-current-v3-missing-source-proof',
               'case_id': HERE.name + '__' + args.suffix,
               'candidate_id': 'primary', 'removed': 'native-raw-actors.jsonl',
               'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
               'manifest_sha256': sha(HERE / 'current-v3-draft-manifest.json'),
               'command': ' '.join(command), 'exit_code': completed.returncode,
               'log_sha256': sha(log), 'files': paths,
               'recorded_only': True, 'missing_evidence': True,
               'native_replay_requested': False}
    result = returned / 'summary.json'
    result.write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'case': args.suffix, 'proof_sha256': sha(result)}))


if __name__ == '__main__':
    main()
