"""Reprocess each exact candidate from recorded-only fixture inputs."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import uuid


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-construction-manifest.json'
SCRATCH = ROOT / '.runtime-work/c24805-selected'
VALIDATOR = ROOT / '.runtime-work/c104538-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(line.rstrip() for line in
                                source.read_text().rstrip().splitlines()) + '\n')


def prove(record):
    case = record['case_id']
    candidate = record['candidate_id']
    source = ROOT / record['source_output']
    compatibility = json.loads((source / 'compatibility.json').read_text())
    if compatibility.get('passed') is not True or compatibility.get('case_id') != case:
        raise ValueError('Public compatibility missing for exact saved case')
    scratch = SCRATCH / f'saved-{case.rsplit("__", 1)[1]}-{candidate}-{uuid.uuid4().hex[:8]}'
    attempt, processed = scratch / 'attempt', scratch / 'processed'
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH / 'output'),
               TMPDIR=str(SCRATCH), PYTHONDONTWRITEBYTECODE='1')
    materialize = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                   'materialize', '--manifest', str(MANIFEST.relative_to(ROOT)),
                   '--case', case, '--candidate', candidate, '--output', str(attempt)]
    run = subprocess.run(materialize, cwd=ROOT, env=env, capture_output=True,
                         text=True, check=False)
    if run.returncode:
        raise RuntimeError('Materialize failed: ' + run.stderr[-1200:])
    for relative, digest in compatibility['fixture_manifest'].items():
        target = attempt / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / relative, target)
        if target.suffix != '.mkv' and sha(target) != digest:
            raise ValueError('Recorded source copy differs: ' + relative)
    before = {name: sha(attempt / name) for name in compatibility['fixture_manifest']}
    command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
               'process-saved', '--manifest', str(MANIFEST.relative_to(ROOT)),
               '--case', case, '--attempt', str(attempt), '--output', str(processed),
               '--library', 'runtime/library', '--validator', str(VALIDATOR.relative_to(ROOT))]
    run = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                         text=True, check=False, timeout=1800)
    target = HERE / 'selected-saved' / f'{case.rsplit("__", 1)[1]}-{candidate}'
    target.mkdir(parents=True, exist_ok=True)
    cli_log = target / 'cli.log'
    cli_log.write_text('\n'.join(line.rstrip() for line in
                                 (run.stdout + run.stderr).rstrip().splitlines()) + '\n')
    if run.returncode:
        raise RuntimeError(f'Saved processing failed for {case}/{candidate}: {cli_log}')
    receipt = json.loads(run.stdout)
    preserved = all(sha(attempt / name) == digest for name, digest in before.items())
    if not receipt.get('passed') or receipt.get('missing_evidence') or not preserved:
        raise ValueError('Recorded-only source preservation failed')
    analysis = processed / 'v0001/analysis.log'
    copy_clean(analysis, target / 'analysis.log')
    report = {'format': 'c24805-selected-saved-proof-v1', 'case_id': case,
              'candidate_id': candidate, 'manifest_sha256': sha(MANIFEST),
              'compatibility_sha256': sha(source / 'compatibility.json'),
              'source_files': len(before), 'source_hashes_preserved': True,
              'processing_receipt': receipt, 'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    target_report = target / 'processing.json'
    target_report.write_text(json.dumps(report, indent=2) + '\n')
    return {'case_id': case, 'candidate_id': candidate,
            'receipt': target_report.relative_to(HERE).as_posix(),
            'receipt_sha256': sha(target_report),
            'analysis_log_sha256': sha(target / 'analysis.log'),
            'cli_log_sha256': sha(cli_log)}


def main():
    compatibility = json.loads((HERE / 'selected-compatibility-proofs.json').read_text())
    records = []
    for record in compatibility['proofs']:
        result = prove(record)
        records.append(result)
        print(json.dumps({'case_id': result['case_id'],
                          'candidate_id': result['candidate_id'],
                          'passed': True}), flush=True)
    target = HERE / 'selected-saved-proofs.json'
    target.write_text(json.dumps({'format': 'c24805-saved-proofs-v1',
                                  'proofs': records}, indent=2) + '\n')
    print(json.dumps({'proof_count': len(records), 'sha256': sha(target)},
                     sort_keys=True))


if __name__ == '__main__':
    main()
