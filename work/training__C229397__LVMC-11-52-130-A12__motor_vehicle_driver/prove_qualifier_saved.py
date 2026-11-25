"""Recorded-only diagnostic paths for exact, unselected qualifier candidates."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from prove_qualifier_finalizer import prepare


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
MANIFEST = HERE / 'qualifier-saved-package/execution-manifest.json'
DECODER = ROOT / '.runtime-work/c150129-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(suffix, stem, kind):
    attempt = prepare(suffix, 'recorded-' + kind)
    selected = json.loads((attempt / 'candidate-selection.json').read_text())
    selected['manifest_sha256'] = sha(MANIFEST)
    (attempt / 'candidate-selection.json').write_text(json.dumps(selected, indent=2) + '\n')
    if kind == 'missing':
        (attempt / ('traffic-actors.jsonl' if stem == 'traffic' else 'device-states.jsonl')).unlink()
    output = ROOT / ('.runtime-work/c229397-qualifier-' + stem + '-saved-' + kind + '-v4')
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
        '--manifest', str(MANIFEST), '--case', ASSIGNMENT + '__' + suffix,
        '--attempt', str(attempt), '--output', str(output),
        '--library', str(ROOT / 'runtime/library'), '--validator', str(DECODER)]
    env = dict(os.environ)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work')
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True)
    log = HERE / ('qualifier-' + stem + '-saved-' + kind + '.log')
    log.write_text(result.stdout + result.stderr)
    receipt = output / 'v0001/processing.json'
    feedback = output / 'v0001/feedback.json'
    if result.returncode or not receipt.is_file():
        raise ValueError(f'{suffix} {kind} recorded-only path failed: ' +
                         (feedback.read_text()[-1200:] if feedback.is_file() else result.stderr[-1200:]))
    value = json.loads(receipt.read_text())
    if value.get('recorded_only') is not True or value.get('originals_preserved') is not True:
        raise ValueError('Saved qualifier proof did not preserve original sources')
    if kind == 'positive':
        if value.get('missing_evidence') is not False or not value.get('final_video_checks'):
            raise ValueError('Positive qualifier saved path lacks final decode')
    else:
        feedback_value = json.loads(feedback.read_text())
        if (value.get('missing_evidence') is not True or
                feedback_value.get('native_replay_requested') is not False):
            raise ValueError('Missing qualifier source did not yield saved-only feedback')
    return {'receipt_sha256': sha(receipt), 'log_sha256': sha(log),
            'missing_evidence': value['missing_evidence'],
            'final_video_decoded': value.get('final_video_checks') is not None}


def main():
    results = {}
    for suffix, stem in (('traffic_conflict_near', 'traffic'),
                         ('device_direction_near', 'device')):
        results[suffix] = {'positive': run(suffix, stem, 'positive'),
                           'missing': run(suffix, stem, 'missing')}
    print(json.dumps({'passed': True, 'diagnostic_fixture': True,
                      'recorded_only': True, 'cases': results,
                      'legal_verdict_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
