"""Prove one combined-manifest candidate through source-only saved processing."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE / 'native'))
from stage_combined_diagnostic import stage

MANIFEST = PACKAGE / 'draft-combined-capture-manifest.json'
LIBRARY = REPO / 'runtime/pipeline/library'
VALIDATOR = REPO / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, env):
    with log.open('w') as stream:
        subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                       stderr=subprocess.STDOUT, check=True)


def prove(short, candidate):
    manifest = json.loads(MANIFEST.read_text())
    case = PACKAGE.name + '__' + short
    entry = next(row for row in manifest['cases'] if row['case_id'] == case)
    selected = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    label = short + '-' + candidate
    base = REPO / '.runtime-work' / ('c183370-update116-combined-' + label)
    compat, source, saved = (Path(str(base) + suffix) for suffix in
                             ('-compat', '-source', '-saved'))
    logs = {name: PACKAGE / ('update116-combined-' + label + '-' + name + '.log')
            for name in ('compat', 'stage', 'saved')}
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/pipeline-output-c183370-update116')
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
    selection = json.loads((compat / 'candidate-selection.json').read_text())
    receipt = json.loads((compat / 'compatibility.json').read_text())
    processed = json.loads((saved / 'v0001/processing.json').read_text())
    result = json.loads((saved / 'v0001/analysis/result.json').read_text())
    assert selection['manifest_sha256'] == sha(MANIFEST)
    assert selection['construction_sha256'] == receipt['construction_sha256'] == \
        processed['analysis_revision']['construction_sha256'] == selected['construction_sha256']
    assert receipt['passed'] is True and receipt['negative_removed'] == 'live-readback.json'
    assert processed['passed'] is True and processed['recorded_only'] is True
    assert processed['originals_preserved'] is True and processed['missing_evidence'] is False
    assert processed['timestamp_joins']['frames'] == 600
    assert result['accepted'] is False and result['legal_verdict_claimed'] is False
    row = {'case_id': case, 'candidate_id': candidate,
           'manifest_sha256': sha(MANIFEST),
           'construction_sha256': selected['construction_sha256'],
           'compatibility_receipt_sha256': sha(compat / 'compatibility.json'),
           'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
           'logs': {name: sha(path) for name, path in logs.items()},
           'diagnostic_only': True, 'passed': True}
    path = PACKAGE / ('update116-combined-' + label + '-proof.json')
    path.write_text(json.dumps(row, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case': short, 'candidate': candidate,
                      'proof_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-suffix', required=True)
    parser.add_argument('--candidate', default='primary')
    args = parser.parse_args()
    prove(args.case_suffix, args.candidate)
