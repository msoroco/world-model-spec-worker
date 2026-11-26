"""Exercise selected saved processing without launching CARLA for each exact case."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'
VALIDATOR = REPO / '.runtime-work/c102372-active-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def invoke(args, env, label):
    result = subprocess.run([sys.executable, '-B', 'runtime.py', *args], cwd=REPO,
                            env=env, text=True, capture_output=True, timeout=900)
    if result.returncode:
        raise RuntimeError(label + ': ' + (result.stderr or result.stdout)[-4000:])
    return result.stdout


def prove():
    manifest = json.loads(MANIFEST.read_text())
    env = dict(os.environ)
    env['TMPDIR'] = str(REPO / '.runtime-work')
    env['MPLCONFIGDIR'] = str(REPO / '.runtime-work/mpl')
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(REPO / '.runtime-work/c255451-recorded-runtime')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        fixture = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-fixture')
        attempt = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-attempt')
        processed = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-processed')
        if any(path.exists() for path in (fixture, attempt, processed)):
            raise ValueError('Choose fresh saved proof output for ' + condition)
        print('recorded-only ' + condition, flush=True)
        invoke(['materialize', '--manifest', str(MANIFEST.relative_to(REPO)),
                '--case', entry['case_id'], '--output', str(attempt.relative_to(REPO))], env, 'materialize ' + condition)
        invoke(['fixture', '--recipe', entry['fixture_recipe'],
                '--output', str(fixture.relative_to(REPO))], env, 'fixture ' + condition)
        for item in fixture.iterdir():
            target = attempt / item.name
            if target.exists():
                raise ValueError('Fixture shadows selected construction: ' + item.name)
            if item.is_dir():
                shutil.copytree(item, target)
            else:
                shutil.copy2(item, target)
        command = ['process-saved', '--manifest', str(MANIFEST.relative_to(REPO)),
                   '--case', entry['case_id'], '--attempt', str(attempt.relative_to(REPO)),
                   '--output', str(processed.relative_to(REPO)), '--library', 'runtime/library',
                   '--validator', str(VALIDATOR.relative_to(REPO))]
        stdout = invoke(command, env, 'process-saved ' + condition)
        receipt = json.loads((processed / 'v0001/processing.json').read_text())
        if not receipt.get('passed') or not receipt.get('recorded_only') or receipt.get('missing_evidence') or not receipt.get('originals_preserved') or receipt.get('candidate_id') != 'primary':
            raise AssertionError('Recorded-only selected processing incomplete: ' + condition)
        log = HERE / 'selected' / condition / 'recorded-only.log'
        log.write_text(stdout.rstrip() + '\n')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': 'runtime.py process-saved --manifest ' + str(MANIFEST.relative_to(REPO))
                       + ' --case ' + entry['case_id']
                       + ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"'
                       + ' --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_log': str(log.relative_to(ROOT)), 'test_log_sha256': sha(log),
            'test_exit_code': 0,
        }
        temporary = REPO / '.runtime-work/c255451-manifest-recorded-next.json'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(MANIFEST)
        print('bound recorded-only ' + condition, flush=True)


if __name__ == '__main__':
    prove()
