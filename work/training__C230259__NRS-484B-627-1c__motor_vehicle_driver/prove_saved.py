"""Exercise selected saved-only analysis on fresh diagnostic acquisitions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c230259_627_decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log=None):
    env = os.environ.copy()
    env['TMPDIR'] = str(ROOT / '.runtime-work')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c230259_627_runtime')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if log:
        with log.open('w') as output:
            completed = subprocess.run(command, cwd=ROOT, env=env,
                                       stdout=output, stderr=subprocess.STDOUT, timeout=600)
        log.write_text(log.read_text().rstrip() + '\n')
    else:
        completed = subprocess.run(command, cwd=ROOT, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                                   text=True, timeout=600)
    if completed.returncode:
        raise RuntimeError('Saved proof command failed: ' + str(log or command))


def one(entry, candidate):
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    label = suffix + '-' + candidate
    scratch = ROOT / '.runtime-work' / ('c230259_627_saved_' + label + '_v1')
    source = scratch / 'source'
    attempt = scratch / 'attempt'
    output = scratch / 'output'
    if scratch.exists():
        proof = entry['post_capture'] if candidate == 'primary' else entry['candidates'][0].get('post_capture', {})
        receipt = HERE / ('saved-' + label + '-processing.json')
        if (proof.get('processing_receipt') == receipt.name and receipt.is_file()
                and proof.get('processing_sha256') == sha(receipt)):
            print(json.dumps({'case_id': entry['case_id'], 'candidate': candidate,
                              'processing_sha256': sha(receipt), 'reused': True}), flush=True)
            return
        raise ValueError('Retain existing saved proof; choose a new version: ' + str(scratch))
    scratch.mkdir(parents=True)
    recipe = ROOT / entry['fixture_recipe']
    run(['.venv-cpu/bin/python', '-B', 'runtime.py', 'fixture',
         '--recipe', str(recipe.relative_to(ROOT)), '--output', str(source.relative_to(ROOT))])
    run(['.venv-cpu/bin/python', '-B', 'runtime.py', 'materialize',
         '--manifest', str(MANIFEST.relative_to(ROOT)), '--case', entry['case_id'],
         '--candidate', candidate, '--output', str(attempt.relative_to(ROOT))])
    for path in source.iterdir():
        dest = attempt / path.name
        if dest.exists():
            raise ValueError('Fixture shadows construction: ' + path.name)
        if path.is_dir():
            shutil.copytree(path, dest)
        else:
            shutil.copyfile(path, dest)
    command = ['.venv-cpu/bin/python', '-B', 'runtime.py', 'process-saved',
               '--manifest', str(MANIFEST.relative_to(ROOT)), '--case', entry['case_id'],
               '--attempt', str(attempt.relative_to(ROOT)),
               '--output', str(output.relative_to(ROOT)),
               '--library', 'runtime/library',
               '--validator', str(VALIDATOR.relative_to(ROOT))]
    log = HERE / ('saved-' + label + '.log')
    run(command, log)
    receipt = output / 'v0001/processing.json'
    data = json.loads(receipt.read_text())
    if (data.get('passed') is not True or data.get('recorded_only') is not True
            or data.get('case_id') != entry['case_id']
            or data.get('candidate_id') != candidate
            or data.get('originals_preserved') is not True
            or data.get('missing_evidence') is not False
            or data.get('legal_acceptance_claimed') is not False):
        raise ValueError('Saved-only proof incomplete: ' + label)
    target = HERE / ('saved-' + label + '-processing.json')
    shutil.copyfile(receipt, target)
    proof = {'recorded_only': True, 'command': ' '.join(command),
             'test_exit_code': 0, 'test_log': log.name,
             'test_log_sha256': sha(log),
             'processing_receipt': target.name, 'processing_sha256': sha(target),
             'originals_preserved': True, 'native_replay_requested': False}
    if candidate == 'primary':
        entry['post_capture'].update(proof)
    else:
        entry['candidates'][0]['post_capture'] = proof
    print(json.dumps({'case_id': entry['case_id'], 'candidate': candidate,
                      'processing_sha256': sha(target)}), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--suffix', choices=('witness_1', 'witness_2',
                                             'exception_1_1', 'exception_1_2'))
    parser.add_argument('--candidate', choices=('primary', 'fallback1'))
    args = parser.parse_args()
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        if args.suffix and not entry['case_id'].endswith('__' + args.suffix):
            continue
        for candidate in ('primary', 'fallback1'):
            if args.candidate and candidate != args.candidate:
                continue
            one(entry, candidate)
            MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
