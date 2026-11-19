"""Run current warning-person candidate positive, negative and saved CPU proofs."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

from stage_diagnostic import stage

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-measured-candidate-manifest.json'
LIBRARY = REPO / 'runtime/pipeline/library'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, env):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    digest = sha(MANIFEST)
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/pipeline-output-c183370-update114')
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        route = case.rsplit('__', 1)[1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = entry if candidate == 'primary' else next(
                c for c in entry['candidates'] if c['id'] == candidate)
            label = route + '-' + candidate
            base = REPO / '.runtime-work' / ('c183370-update114-person-refresh-' + label)
            compat, source, saved = [Path(str(base) + suffix) for suffix in
                                     ('-compat', '-source', '-saved')]
            logs = {name: PACKAGE / ('update114-' + label + '-' + name + '.log')
                    for name in ('compat', 'stage', 'saved')}
            common = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')]
            run(common + ['compatibility', '--manifest', str(MANIFEST), '--case', case,
                          '--candidate', candidate, '--output', str(compat),
                          '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
                logs['compat'], env)
            with logs['stage'].open('w') as stream:
                print(stage(case, candidate, compat, source), file=stream)
            run(common + ['process-saved', '--manifest', str(MANIFEST), '--case', case,
                          '--attempt', str(source), '--output', str(saved),
                          '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
                logs['saved'], env)
            proof = json.loads((compat / 'compatibility.json').read_text())
            processed = json.loads((saved / 'v0001/processing.json').read_text())
            if (proof.get('passed') is not True or processed.get('passed') is not True or
                    processed.get('missing_evidence') is not False or
                    processed.get('originals_preserved') is not True):
                raise ValueError('Sign candidate CPU proof failed: ' + label)
            rows.append({'case_id': case, 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                         'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
                         'logs': {name: sha(log) for name, log in logs.items()}})
            progress = PACKAGE / 'update114-person-candidate-progress.json'
            progress.write_text(json.dumps({'format': 'c183370-person-candidate-progress-v1',
                                            'manifest_sha256': digest, 'rows': rows},
                                           indent=2, sort_keys=True) + '\n')
            print(label, 'passed', flush=True)
    final = PACKAGE / 'update114-person-candidate-matrix.json'
    final.write_text(json.dumps({'format': 'c183370-person-candidate-matrix-v1',
                                 'manifest_sha256': digest, 'rows': rows},
                                indent=2, sort_keys=True) + '\n')
    return final


if __name__ == '__main__':
    print(prove())
