"""Run pinned offline, compatibility, and saved CPU proofs for barrier candidates."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from stage_variant_diagnostic import stage

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'draft-barrier-capture-manifest.json'
LIBRARY = REPO / 'runtime/pipeline/library'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, env):
    with log.open('w') as output:
        subprocess.run(command, cwd=REPO, env=env, stdout=output,
                       stderr=subprocess.STDOUT, check=True)


def prove(routes, candidates, update):
    if not VALIDATOR.is_file():
        raise ValueError('Current pinned decoder is missing')
    manifest = json.loads(MANIFEST.read_text())
    manifest_sha = sha(MANIFEST)
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work' /
                                                ('pipeline-output-c183370-' + update))
    rows = []
    for route in routes:
        case = PACKAGE.name + '__barrier_' + route
        entry = next(row for row in manifest['cases'] if row['case_id'] == case)
        for candidate in candidates:
            selected = (entry if candidate == 'primary' else
                        next(row for row in entry['candidates'] if row['id'] == candidate))
            base = 'c183370-' + update + '-barrier-' + route + '-' + candidate
            output = REPO / '.runtime-work'
            offline = output / (base + '-offline')
            compat = output / (base + '-compat')
            source = output / (base + '-source')
            saved = output / (base + '-saved')
            logs = {name: PACKAGE / (update + '-barrier-' + route + '-' + candidate + '-' + name + '.log')
                    for name in ('offline', 'compat', 'stage', 'saved')}
            common = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py')]
            run(common + ['offline', '--manifest', str(MANIFEST), '--case', case,
                          '--candidate', candidate, '--output', str(offline),
                          '--python', str(REPO / '.venv-cpu/bin/python')],
                logs['offline'], env)
            run(common + ['compatibility', '--manifest', str(MANIFEST), '--case', case,
                          '--candidate', candidate, '--output', str(compat),
                          '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
                logs['compat'], env)
            with logs['stage'].open('w') as stream:
                print(stage(route, compat, source, candidate), file=stream)
            run(common + ['process-saved', '--manifest', str(MANIFEST), '--case', case,
                          '--attempt', str(source), '--output', str(saved),
                          '--library', str(LIBRARY), '--validator', str(VALIDATOR)],
                logs['saved'], env)
            proof = json.loads((compat / 'compatibility.json').read_text())
            processed = json.loads((saved / 'v0001/processing.json').read_text())
            if (proof.get('passed') is not True or processed.get('passed') is not True or
                    processed.get('missing_evidence') is not False or
                    processed.get('originals_preserved') is not True):
                raise ValueError('Barrier candidate did not pass all CPU proof checks: ' + base)
            rows.append({'case_id': case, 'candidate': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'manifest_sha256': manifest_sha,
                         'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
                         'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
                         'logs': {name: {'path': log.name, 'sha256': sha(log)}
                                  for name, log in logs.items()}})
            (PACKAGE / (update + '-barrier-candidate-progress.json')).write_text(
                json.dumps({'format': 'c183370-barrier-candidate-progress-v1',
                            'manifest_sha256': manifest_sha, 'completed': rows},
                           indent=2, sort_keys=True) + '\n')
            print(route, candidate, 'offline/compatibility/saved passed', flush=True)
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--update', default='update112')
    parser.add_argument('--routes', nargs='+', default=['crossing', 'avoidance'])
    parser.add_argument('--candidates', nargs='+', default=['primary', 'fallback1',
                                                             'fallback2', 'fallback3'])
    args = parser.parse_args()
    prove(args.routes, args.candidates, args.update)
