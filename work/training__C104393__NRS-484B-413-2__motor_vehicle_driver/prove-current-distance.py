"""Run current-runtime synthetic compatibility and saved-source diagnostics."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PYTHON = ROOT / '.venv-cpu/bin/python'
CASE_PREFIX = 'training__C104393__NRS-484B-413-2__motor_vehicle_driver'
VALIDATOR = ROOT / '.runtime-work/c110812-current-decoder/.lake/build/bin/adapterCheck'
LIBRARY = ROOT / 'runtime/pipeline/library'


def run(args, log, expected=0):
    with (HERE / log).open('w') as output:
        result = subprocess.run([str(PYTHON), str(ROOT / 'runtime.py'), *map(str, args)],
                                cwd=ROOT, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode != expected:
        raise RuntimeError(f'{log}: exit {result.returncode}, expected {expected}')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_proof(feet, candidate):
    source = ROOT / f'.runtime-work/c104393-current-v3-{feet}-{candidate}'
    item = {'candidate_id': candidate,
            'recipe': f"diagnostic-{feet}{'-fallback1' if candidate == 'fallback1' else ''}-recipe.json"}
    for key, src, suffix in [('receipt', 'compatibility.json', 'receipt.json'),
                             ('analysis_log', 'compatibility-analysis.log', 'analysis.log'),
                             ('negative_log', 'negative-analysis.log', 'negative.log')]:
        target = f'current-v2-{feet}-{candidate}-{suffix}'
        shutil.copy2(source / src, HERE / target)
        item[key] = target
    item['sha256'] = sha(HERE / item['receipt'])
    return item


def compat(feet, candidate):
    manifest = (f'diagnostic-{feet}-fallback1-manifest.json' if candidate == 'fallback1'
                else 'draft-execution-manifest.json')
    run(['compatibility', '--manifest', HERE / manifest, '--case', f'{CASE_PREFIX}__{feet}',
         '--candidate', candidate, '--output', ROOT / f'.runtime-work/c104393-current-v3-{feet}-{candidate}',
         '--library', LIBRARY, '--validator', VALIDATOR], f'current-v2-{feet}-{candidate}.log')
    return copy_proof(feet, candidate)


def saved(feet):
    fixture = ROOT / f'.runtime-work/c104393-{feet}-saved-fixture'
    attempt = ROOT / f'.runtime-work/c104393-{feet}-v3-saved-attempt'
    output = ROOT / f'.runtime-work/c104393-{feet}-v3-saved-output'
    negative_attempt = ROOT / f'.runtime-work/c104393-{feet}-v3-saved-negative-attempt'
    negative_output = ROOT / f'.runtime-work/c104393-{feet}-v3-saved-negative-output'
    manifest = HERE / 'draft-execution-manifest.json'
    case = f'{CASE_PREFIX}__{feet}'
    if not fixture.exists():
        run(['fixture', '--recipe', HERE / f'diagnostic-{feet}-recipe.json', '--output', fixture],
            f'current-{feet}-saved-fixture.log')
    run(['materialize', '--manifest', manifest, '--case', case, '--output', attempt],
        f'current-{feet}-saved-materialize.log')
    for source in fixture.iterdir():
        target = attempt / source.name
        if target.exists():
            raise RuntimeError(f'Collision in saved attempt: {target}')
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            shutil.copy2(source, target)
    run(['process-saved', '--manifest', manifest, '--case', case, '--attempt', attempt,
         '--output', output, '--library', LIBRARY, '--validator', VALIDATOR],
        f'current-{feet}-saved-processing.log')
    receipt = output / 'v0001/processing.json'
    proof = json.loads(receipt.read_text())
    if not (proof['passed'] and proof['recorded_only'] and not proof['missing_evidence'] and
            not proof['physical_acceptance_claimed'] and not proof['legal_acceptance_claimed']):
        raise RuntimeError(f'Unexpected saved positive receipt for {feet}')
    shutil.copy2(receipt, HERE / f'current-{feet}-saved-processing-receipt.json')
    shutil.copy2(output / 'v0001/analysis.log', HERE / f'current-{feet}-saved-analysis.log')
    shutil.copytree(attempt, negative_attempt)
    (negative_attempt / 'native_samples.jsonl').unlink()
    run(['process-saved', '--manifest', manifest, '--case', case, '--attempt', negative_attempt,
         '--output', negative_output, '--library', LIBRARY, '--validator', VALIDATOR],
        f'current-{feet}-saved-negative.log', expected=1)
    feedback = negative_output / 'v0001/feedback.json'
    if 'Missing required source: native_samples.jsonl' not in json.loads(feedback.read_text())['error']:
        raise RuntimeError(f'Missing-source negative did not reject for {feet}')
    shutil.copy2(feedback, HERE / f'current-{feet}-saved-negative-feedback.json')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--feet', type=int, required=True, choices=(90, 100, 110, 290, 300, 310))
    parser.add_argument('--skip-compat', action='store_true')
    args = parser.parse_args()
    feet = args.feet
    candidates = ('primary', 'fallback1', 'fallback2', 'fallback3')
    if args.skip_compat:
        items = [copy_proof(feet, candidate) for candidate in candidates]
    else:
        with ThreadPoolExecutor(max_workers=4) as pool:
            items = list(pool.map(lambda candidate: compat(feet, candidate), candidates))
    summary = {'format': 'c104393-current-v2-unselected-summary',
               'case_id': f'{CASE_PREFIX}__{feet}', 'candidate_receipts': items,
               'physical_success_claimed': False}
    (HERE / f'current-v2-{feet}-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    with (HERE / f'current-v2-{feet}-audit.log').open('w') as audit_log:
        audit = subprocess.run([str(PYTHON), str(HERE / 'audit-current-300.py'),
                                '--feet', str(feet)], cwd=ROOT, stdout=audit_log,
                               stderr=subprocess.STDOUT)
    if audit.returncode:
        raise RuntimeError(f'current-v2-{feet}-audit.log: exit {audit.returncode}')
    saved(feet)
    print(json.dumps({'feet': feet, 'candidates': len(items), 'saved_positive': True,
                      'missing_source_negative': True}))


if __name__ == '__main__':
    main()
