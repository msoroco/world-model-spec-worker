"""Exercise exact recorded-only processing on fresh synthetic attempts."""
import concurrent.futures
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    folder = Path(__file__).resolve().parent
    repo = folder.parents[1]
    sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
    from worker_exchange.fixture_recipe import materialize
    from worker_exchange.package_compatibility import materialize_case
    manifest_path = folder / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    scratch = next(repo / '.runtime-work' / f'c229439-saved-v{index}'
                   for index in range(2, 100)
                   if not (repo / '.runtime-work' / f'c229439-saved-v{index}').exists())
    scratch.mkdir()
    validator = repo / '.runtime-work/c229439-validator/.lake/build/bin/adapterCheck'

    def run(entry):
        short = entry['case_id'].rsplit('__', 1)[-1]
        base = scratch / short
        base.mkdir()
        fixture = base / 'fixture'
        materialize(repo, repo / entry['fixture_recipe'], fixture)
        attempt = base / 'attempt'
        materialize_case(manifest_path, entry['case_id'], attempt, fixture)
        command = [sys.executable, str(repo / 'runtime.py'), 'process-saved',
                   '--manifest', str(manifest_path), '--case', entry['case_id'],
                   '--attempt', str(attempt), '--output', str(base / 'positive-versions'),
                   '--library', str(repo / 'runtime/library'), '--validator', str(validator)]
        positive_log = base / 'positive-command.log'
        with positive_log.open('x') as log:
            positive = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                      env=os.environ.copy(), timeout=1200)
        if positive.returncode:
            raise ValueError(short + ': saved positive failed: ' + positive_log.read_text()[-1400:])
        processing = base / 'positive-versions/v0001/processing.json'
        result = json.loads(processing.read_text())
        if result.get('passed') is not True or result.get('recorded_only') is not True:
            raise ValueError(short + ': selected saved-only receipt incomplete')
        negative_attempt = base / 'negative-attempt'
        shutil.copytree(attempt, negative_attempt)
        (negative_attempt / 'device-source.json').unlink()
        negative_command = command.copy()
        negative_command[negative_command.index('--attempt') + 1] = str(negative_attempt)
        negative_command[negative_command.index('--output') + 1] = str(base / 'negative-versions')
        negative_log = base / 'negative-command.log'
        with negative_log.open('x') as log:
            negative = subprocess.run(negative_command, stdout=log, stderr=subprocess.STDOUT,
                                      env=os.environ.copy(), timeout=1200)
        feedback = base / 'negative-versions/v0001/feedback.json'
        if not feedback.is_file():
            raise ValueError(short + ': missing-source saved feedback absent')
        response = json.loads(feedback.read_text())
        if ('Missing required source: device-source.json' not in str(response) or
                response.get('native_replay_requested') is not False):
            raise ValueError(short + ': saved negative did not reject source without replay: ' + str(response)[:600])
        return short, command, negative_command, processing, positive_log, negative_log, feedback, negative.returncode

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        outputs = list(pool.map(run, manifest['cases']))
    for short, command, negative_command, processing, positive_log, negative_log, feedback, negative_exit in outputs:
        case_dir = folder / 'cases' / short
        for source, name in ((processing, 'saved-processing.json'), (positive_log, 'saved-positive.log'),
                             (negative_log, 'saved-negative.log'), (feedback, 'saved-negative-feedback.json')):
            target = case_dir / name
            text = source.read_text().rstrip() + '\n'
            target.write_text(text)
        entry = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + short))
        entry['post_capture'] = {'recorded_only': True, 'command': ' '.join(command),
                                 'feedback_command': ' '.join(negative_command),
                                 'test_log': f'cases/{short}/saved-positive.log',
                                 'test_log_sha256': sha(case_dir / 'saved-positive.log'),
                                 'test_exit_code': 0,
                                 'negative_exit_code': negative_exit,
                                 'negative_log': f'cases/{short}/saved-negative.log',
                                 'negative_log_sha256': sha(case_dir / 'saved-negative.log'),
                                 'negative_feedback': f'cases/{short}/saved-negative-feedback.json',
                                 'negative_feedback_sha256': sha(case_dir / 'saved-negative-feedback.json'),
                                 'receipt': f'cases/{short}/saved-processing.json',
                                 'receipt_sha256': sha(case_dir / 'saved-processing.json')}
        print(short + ': recorded-only positive and missing-source feedback passed', flush=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
