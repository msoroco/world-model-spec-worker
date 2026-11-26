"""Prove recorded-only processing on exact positive compatibility acquisitions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/nrs213-resume-5'
CASES = ('probe_a', 'probe_b', 'curve_right', 'curve_left',
         'one_way_crest', 'one_way_curve')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def run(suffix, candidate):
    manifest = HERE / 'execution-manifest.json'
    data = json.loads(manifest.read_text())
    case = HERE.name + '__' + suffix
    entry = next(item for item in data['cases'] if item['case_id'] == case)
    selected = entry if candidate == 'primary' else entry['candidates'][0]
    attempt = SCRATCH / ('compat-' + candidate + '-' + suffix)
    selection_path = attempt / 'candidate-selection.json'
    if candidate == 'primary':
        selection_path.unlink(missing_ok=True)
    else:
        save(selection_path, {'format': 'worker-candidate-selection',
                              'case_id': case, 'candidate_id': candidate,
                              'construction_sha256': selected['construction_sha256'],
                              'manifest_sha256': sha(manifest)})
    output = SCRATCH / ('saved-' + candidate + '-' + suffix)
    command = [sys.executable, '-B', str(REPO / 'runtime.py'), 'process-saved',
               '--manifest', str(manifest), '--case', case,
               '--attempt', str(attempt), '--output', str(output),
               '--library', str(REPO / 'runtime/library'),
               '--validator', str(REPO / '.runtime-work/nrs213-resume/current-decoder/.lake/build/bin/adapterCheck')]
    stdout = SCRATCH / ('saved-' + candidate + '-' + suffix + '.stdout')
    with stdout.open('w') as stream:
        completed = subprocess.run(command, cwd=REPO, env=os.environ.copy(),
                                   stdout=stream, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError('Recorded-only processing failed: ' + str(stdout))
    versions = sorted(output.glob('v*/processing.json'))
    if not versions:
        raise RuntimeError('Recorded-only processing receipt missing: ' + str(output))
    source = versions[-1]
    receipt = json.loads(source.read_text())
    if (receipt.get('passed') is not True or receipt.get('recorded_only') is not True
            or receipt.get('originals_preserved') is not True
            or receipt.get('candidate_id') != candidate or receipt.get('case_id') != case
            or receipt.get('analysis_revision', {}).get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Recorded-only proof differs from exact candidate')
    target = HERE / 'saved-proofs' / (candidate + '-' + suffix + '-processing.json')
    target.parent.mkdir(exist_ok=True)
    shutil.copyfile(source, target)
    if target.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('Recorded-only receipt exceeds work file limit')
    summary = {'format': 'c230259-213-2a-recorded-only-cpu-test-v1',
               'case_id': case, 'candidate_id': candidate,
               'command': ' '.join(command), 'exit_code': 0,
               'raw_stdout_sha256': sha(stdout),
               'processing_receipt': str(target.relative_to(HERE)),
               'processing_receipt_sha256': sha(target),
               'recorded_only': True, 'originals_preserved': True,
               'native_replay_requested': False,
               'analysis_revision_construction_sha256': selected['construction_sha256']}
    log = HERE / 'saved-proofs' / (candidate + '-' + suffix + '-test.log')
    save(log, summary)
    print(json.dumps({'case_id': case, 'candidate_id': candidate,
                      'processing_sha256': sha(target), 'test_log_sha256': sha(log)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=CASES, required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), required=True)
    args = parser.parse_args()
    run(args.case, args.candidate)
