"""Exercise current-runtime saved-only processing on source-shaped CPU attempts.

The fixtures are synthetic. This proves the processing and feedback paths, not
physical completion or legal acceptance.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RUNTIME_WORK = ROOT / '.runtime-work/c149470'
MANIFEST = HERE / 'execution-manifest.compatibility-diagnostic.json'
VALIDATOR = ROOT / '.runtime-work/c110969-decoder/.lake/build/bin/adapterCheck'
CASES = [entry['case_id'] for entry in json.loads((HERE / 'execution-manifest.json').read_text())['cases']]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, attempt, output, validator):
    command = [sys.executable, 'runtime.py', 'process-saved', '--manifest', str(MANIFEST),
               '--case', case, '--attempt', str(attempt), '--output', str(output),
               '--library', 'runtime/library', '--validator', str(validator)]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(RUNTIME_WORK / 'postcapture'),
               TMPDIR=str(RUNTIME_WORK / 'tmp'),
               MPLCONFIGDIR=str(RUNTIME_WORK / 'tmp'))
    result = subprocess.run(command, cwd=ROOT, env=env, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    version = max(output.glob('v[0-9][0-9][0-9][0-9]'))
    return result, version


def positive(case):
    name = case.rsplit('__', 1)[-1]
    attempt = RUNTIME_WORK / ('grid10-compat-' + name)
    output = RUNTIME_WORK / 'postcapture' / name
    existing = output / 'v0001/processing.json'
    if existing.is_file() and json.loads(existing.read_text()).get('passed') is True:
        version = existing.parent
        exit_code = 0
    else:
        result, version = run(case, attempt, output, VALIDATOR)
        exit_code = result.returncode
    receipt = json.loads((version / 'processing.json').read_text())
    assert exit_code == 0 and receipt['passed'] is True
    assert receipt['recorded_only'] is True and receipt['originals_preserved'] is True
    assert receipt['timestamp_joins']['frames'] == 900
    assert receipt['final_video_checks']['passed'] is True
    assert receipt['analysis_revision']['construction_sha256'] == digest(attempt / 'construction.json')
    assert receipt['native_revision']['construction_sha256'] == digest(attempt / 'construction.json')
    return name, version, digest(version / 'processing.json')


def negative(case, kind):
    name = case.rsplit('__', 1)[-1]
    original = RUNTIME_WORK / ('grid10-compat-' + name)
    attempt = RUNTIME_WORK / 'postcapture' / ('negative-attempt-' + kind)
    if attempt.exists():
        shutil.rmtree(attempt)
    shutil.copytree(original, attempt, copy_function=os.link)
    if kind == 'missing-source':
        (attempt / 'bus-rows.json').unlink()
        validator = VALIDATOR
    else:
        validator = RUNTIME_WORK / 'postcapture/no-such-validator'
    output = RUNTIME_WORK / 'postcapture' / ('negative-' + kind)
    result, version = run(case, attempt, output, validator)
    feedback = json.loads((version / 'feedback.json').read_text())
    assert feedback['recorded_only'] is True
    assert feedback['native_replay_requested'] is False
    if kind == 'missing-source':
        assert (feedback.get('classification') == 'incomplete_or_unavailable_law_evidence'
                or 'bus-rows.json' in feedback.get('error', ''))
    else:
        assert result.returncode != 0 and ('validator' in feedback.get('error', '').lower()
                                            or 'no-such-validator' in feedback.get('error', ''))
    return kind, result.returncode, version, digest(version / 'feedback.json')


def main():
    (RUNTIME_WORK / 'postcapture').mkdir(parents=True, exist_ok=True)
    (RUNTIME_WORK / 'tmp').mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        positives = list(pool.map(positive, CASES))
    for name, version, checksum in positives:
        print(f'positive {name} exit=0 receipt={version / "processing.json"} sha256={checksum}', flush=True)
    for kind in ('missing-source', 'missing-validator'):
        label, exit_code, version, checksum = negative(CASES[0], kind)
        print(f'feedback {label} exit={exit_code} receipt={version / "feedback.json"} sha256={checksum}', flush=True)


if __name__ == '__main__':
    main()
