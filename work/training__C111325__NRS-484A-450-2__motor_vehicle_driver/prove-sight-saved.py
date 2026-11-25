"""Recorded-only source preservation for one sight-point draft candidate."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-sight-draft-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def trimmed(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip('\n') + '\n')


def prove(label, candidate):
    if label not in ('sight_stop', 'sight_pass') or candidate not in ('primary', 'fallback1'):
        raise ValueError('Unknown sight-point case/candidate')
    case = HERE.name + '__' + label
    source_tag = label.removeprefix('sight_')
    source = ROOT / f'.runtime-work/c111325-selected/compat-sight-v7-{source_tag}-{candidate}'
    compatibility = json.loads((source / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or compatibility.get('case_id') != case:
        raise ValueError('Sight-point public compatibility has not passed')
    scratch = ROOT / f'.runtime-work/c111325-selected/saved-sight-v4-{label}-{candidate}'
    if scratch.exists():
        raise ValueError('Recorded-only scratch must be fresh')
    scratch.mkdir(parents=True)
    attempt, processed = scratch / 'attempt', scratch / 'processed'
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                    '--manifest', str(MANIFEST), '--case', case, '--candidate', candidate,
                    '--output', str(attempt)], check=True, stdout=subprocess.DEVNULL)
    for relative, digest in compatibility['fixture_manifest'].items():
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        if target.suffix != '.mkv' and sha(target) != digest:
            raise ValueError('Sight-point copied source hash differs: ' + relative)
    before = {relative: sha(attempt / relative)
              for relative in compatibility['fixture_manifest']}
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case,
               '--attempt', str(attempt), '--output', str(processed),
               '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    run = subprocess.run(command, capture_output=True, text=True, timeout=1800)
    base = HERE / 'selected-saved' / f'{label}-{candidate}'
    trimmed(base / 'cli.log', run.stdout + run.stderr)
    if run.returncode:
        raise RuntimeError('Sight-point recorded-only processing failed: ' + str(run.returncode))
    receipt = json.loads(run.stdout)
    preserved = all(sha(attempt / name) == digest for name, digest in before.items())
    if not receipt.get('passed') or receipt.get('missing_evidence') or not preserved:
        raise ValueError('Sight-point recorded source preservation failed')
    report = {'format': 'c111325-sight-saved-proof-v1',
              'case_id': case, 'candidate_id': candidate,
              'manifest_sha256': sha(MANIFEST),
              'compatibility_sha256': sha(source / 'compatibility.json'),
              'source_files': len(before), 'source_hashes_preserved': True,
              'processing_receipt': receipt, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    (base / 'processing.json').write_text(json.dumps(report, indent=2) + '\n')
    trimmed(base / 'analysis.log', (processed / 'v0001/analysis.log').read_text())
    return {'case_id': case, 'candidate_id': candidate,
            'proof_sha256': sha(base / 'processing.json')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', choices=('sight_stop', 'sight_pass'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), required=True)
    args = parser.parse_args()
    os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                          str(ROOT / '.runtime-work/c111325-selected/output'))
    print(json.dumps(prove(args.label, args.candidate), sort_keys=True))
