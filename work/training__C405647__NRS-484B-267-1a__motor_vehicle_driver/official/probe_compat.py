"""Run exact pinned v1 portable compatibility on official synthetic fixtures."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SEED = HERE.parent / 'probe-package-compatibility.py'
spec = importlib.util.spec_from_file_location('c405647_portable_seed', SEED)
seed = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seed)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(source, case, candidate, ffmpeg):
    saved = HERE / 'saved-fixtures' / case / candidate
    for name in ('source-scope.json', 'actor-frames.jsonl',
                 'observed-actors.jsonl', 'front-lamp-review.json',
                 'front_lamp.source', 'video_frames.jsonl', 'trace.jsonl'):
        shutil.copyfile(saved / name, source / name)
    for name in ('overview.mkv', 'front_lamp.mkv', 'rear_approach.mkv',
                 'subject_reference.mkv'):
        size = '1920x1080' if name == 'overview.mkv' else '1280x720'
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', f'color=c=blue:s={size}:r=20:d=24',
                        '-c:v', 'ffv1', '-n', str(source / name)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=180)


def prove(case, candidate):
    ffmpeg = REPO / '.runtime-work/linux_arm64/ffmpeg'
    assert ffmpeg.is_file()
    os.environ['PATH'] = str(ffmpeg.parent) + os.pathsep + os.environ.get('PATH', '')
    scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work', prefix='c405647-official-compat-'))
    source = scratch / 'fixture'
    previous = seed.fixture_module._fixture
    seed.fixture_module._fixture = lambda folder, selected_case, tool, full_resolution=False: fixture(
        folder, selected_case, candidate, tool)
    try:
        seed.build(source, case, ffmpeg)
    finally:
        seed.fixture_module._fixture = previous
    case_id = HERE.parent.name + '__' + case
    output = scratch / 'output'
    receipt = seed.run(HERE / 'package-manifest.json', case_id, source, output,
                       REPO / 'runtime/pipeline/library',
                       REPO / '.runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck',
                       candidate)
    negative = scratch / 'negative'
    seed.materialize_case(HERE / 'package-manifest.json', case_id,
                          negative, source, candidate)
    (negative / 'source-scope.json').unlink()
    failure = subprocess.run([sys.executable, str(negative / 'finalize.py'),
                              '--attempt', str(negative), '--output',
                              str(negative / 'analysis-report.json')],
                             cwd=negative, env=seed.execution_env(), text=True,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             timeout=300)
    if failure.returncode == 0 or 'Missing required source: source-scope.json' not in failure.stdout:
        raise AssertionError('Missing-source negative did not reject: ' + failure.stdout[-1000:])
    retained = HERE / 'portable-receipts' / case / candidate
    retained.mkdir(parents=True, exist_ok=True)
    for name in ('compatibility.json', 'final-decode.json',
                 'analysis-report.json', 'result.json'):
        shutil.copyfile(output / name, retained / name)
    shutil.copyfile(output / 'compatibility-analysis.log', retained / 'portable-analysis.log')
    (retained / 'negative-analysis.log').write_text(failure.stdout)
    summary = {'case_id': case_id, 'candidate_id': candidate,
               'manifest_sha256': sha(HERE / 'package-manifest.json'),
               'positive_receipt_sha256': sha(retained / 'compatibility.json'),
               'positive_log_sha256': sha(retained / 'portable-analysis.log'),
               'negative_log_sha256': sha(retained / 'negative-analysis.log'),
               'negative_error': 'Missing required source: source-scope.json',
               'scope': 'unselected exact v1 synthetic compatibility; no Native or accepted recording'}
    (retained / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('official_1', 'official_2'), required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1', 'fallback2', 'fallback3'), required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.case, args.candidate), sort_keys=True))
