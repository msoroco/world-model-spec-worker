"""Exercise recorded-only processing and missing-source feedback per exact case."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
SCRATCH = REPO / '.runtime-work/c229452-saved-v1'
VALIDATOR = REPO / '.runtime-work/c109755-decoder-v2/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cleaned(value):
    return value.rstrip() + '\n' if value.strip() else ''


def run(entry):
    sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.package_compatibility import materialize_case
    cid = entry['case_id']
    short = cid.rsplit('__', 1)[-1]
    base = SCRATCH / short
    base.mkdir(parents=True, exist_ok=True)
    fixture = base / 'fixture'
    materialize(REPO, REPO / entry['fixture_recipe'], fixture)
    attempt = base / 'attempt'
    materialize_case(MANIFEST, cid, attempt, fixture)
    command = [sys.executable, str(REPO / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', cid, '--attempt', str(attempt),
               '--output', str(base / 'positive-versions'), '--library', str(REPO / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(REPO / '.runtime-work'),
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c229452-saved-pipeline'))
    positive = subprocess.run(command, cwd=REPO, env=env, capture_output=True, text=True, timeout=1200)
    if positive.returncode:
        raise ValueError(short + ' saved positive: ' + positive.stderr[-800:])
    processing = base / 'positive-versions/v0001/processing.json'
    result = json.loads(processing.read_text())
    if result.get('passed') is not True or result.get('recorded_only') is not True:
        raise ValueError(short + ' saved receipt incomplete')
    negative_attempt = base / 'negative-attempt'
    shutil.copytree(attempt, negative_attempt)
    (negative_attempt / 'original-red-curb-events.jsonl').unlink()
    negative_command = command.copy()
    negative_command[negative_command.index('--attempt') + 1] = str(negative_attempt)
    negative_command[negative_command.index('--output') + 1] = str(base / 'negative-versions')
    negative = subprocess.run(negative_command, cwd=REPO, env=env,
                              capture_output=True, text=True, timeout=1200)
    feedback = base / 'negative-versions/v0001/feedback.json'
    if not feedback.is_file():
        raise ValueError(short + ' missing saved negative feedback')
    response = json.loads(feedback.read_text())
    expected = 'Missing required source: original-red-curb-events.jsonl'
    if expected not in str(response) or response.get('native_replay_requested') is not False:
        raise ValueError(short + ' saved negative did not reject source without replay')
    return entry, short, command, negative_command, positive, negative, processing, feedback


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        outputs = list(pool.map(run, manifest['cases']))
    for entry, short, command, negative_command, positive, negative, processing, feedback in outputs:
        case_dir = ROOT / 'cases' / short
        artifacts = {
            'saved-processing.json': processing.read_text(),
            'saved-positive.log': positive.stdout + positive.stderr,
            'saved-negative.log': negative.stdout + negative.stderr,
            'saved-negative-feedback.json': feedback.read_text()}
        for name, content in artifacts.items():
            (case_dir / name).write_text(cleaned(content))
        entry['post_capture'] = {'recorded_only': True, 'command': ' '.join(command),
                                 'feedback_command': ' '.join(negative_command),
                                 'test_log': f'cases/{short}/saved-positive.log',
                                 'test_log_sha256': sha(case_dir / 'saved-positive.log'),
                                 'test_exit_code': 0, 'negative_exit_code': negative.returncode,
                                 'negative_log': f'cases/{short}/saved-negative.log',
                                 'negative_log_sha256': sha(case_dir / 'saved-negative.log'),
                                 'negative_feedback': f'cases/{short}/saved-negative-feedback.json',
                                 'negative_feedback_sha256': sha(case_dir / 'saved-negative-feedback.json'),
                                 'receipt': f'cases/{short}/saved-processing.json',
                                 'receipt_sha256': sha(case_dir / 'saved-processing.json')}
        print(short + ': saved-only positive and missing-source feedback passed', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
