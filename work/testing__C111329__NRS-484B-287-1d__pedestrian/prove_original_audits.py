"""Exercise production audit CLIs against labeled, three-frame diagnostic sources."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from saved_process import process

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work/c111329-original-audit-proof'
ORIGINAL = REPO / '.runtime-work/c111329-diagnostic'
SUFFIXES = ('adjacent_no_diagonal_authority', 'diagonal_no_authority',
            'diagonal_authorized', 'adjacent_authorized_device')
PAIRS = {
    'diagonal_path_without_authority': SUFFIXES[:2],
    'diagonal_device_authority': SUFFIXES[1:3],
    'authorized_device_path_control': SUFFIXES[2:4],
}


def run(args: list[str], log: Path, expected: int, contains: str) -> None:
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
               SCENARIO_PIPELINE_OUTPUT_ROOT=str(REPO / '.runtime-work/c111329-runtime-output'))
    completed = subprocess.run(args, cwd=REPO, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.write_text(completed.stdout.rstrip() + '\n', encoding='utf-8')
    if (completed.returncode == 0) != (expected == 0) or contains not in completed.stdout:
        raise ValueError(f'audit proof failed: {log}: {completed.returncode}: {completed.stdout[-700:]}')


def attempt(suffix: str) -> Path:
    target = SCRATCH / suffix
    shutil.copytree(ORIGINAL / suffix, target)
    refs = []
    for name in ('site.json', 'native-acquisition.json', 'camera-manifest.json'):
        shutil.copy2(HERE / 'cases' / suffix / 'diagnostic-sources' / name, target / name)
        refs.append({'path': name, 'sha256': hashlib.sha256((target / name).read_bytes()).hexdigest()})
    process(target, *refs, HERE.name + '__' + suffix, target / 'saved-receipt.json',
            expected_frames=3, allow_diagnostic=True)
    run([sys.executable, str(HERE / 'seal_original_refs.py'), '--attempt', str(target),
         '--output', str(target / 'source-refs.json')],
        HERE / f'cpu-original-source-refs-{suffix}.log', 0, 'sealed original source references')
    return target


def main() -> None:
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)
    roots = {suffix: attempt(suffix) for suffix in SUFFIXES}
    for suffix, root in roots.items():
        case = HERE.name + '__' + suffix
        (HERE / 'cases' / suffix / 'original-audit-diagnostic.json').unlink(missing_ok=True)
        base = [sys.executable, str(HERE / 'original_attempt_audit.py'),
                '--case', case, '--attempt', str(root), '--refs', str(root / 'source-refs.json')]
        run(base + ['--output', str(HERE / 'cases' / suffix / 'original-audit-diagnostic.json'),
                    '--allow-diagnostic', '--expected-frames', '3'],
            HERE / f'cpu-original-audit-{suffix}-positive.log', 0, '"production": false')
        run(base + ['--output', str(SCRATCH / (suffix + '-negative.json'))],
            HERE / f'cpu-original-audit-{suffix}-negative.log', 1, 'unreviewed original site rejected')
        run(base + ['--output', str(SCRATCH / (suffix + '-short-negative.json')),
                    '--expected-frames', '3'],
            HERE / f'cpu-original-audit-{suffix}-short-negative.log', 1, 'pinned 900-frame')
    for name, (first, second) in PAIRS.items():
        left, right = roots[first], roots[second]
        (HERE / 'comparisons' / (name + '.original-diagnostic.json')).unlink(missing_ok=True)
        base = [sys.executable, str(HERE / 'original_comparison_audit.py'),
                '--comparison', name, '--first-attempt', str(left),
                '--first-refs', str(left / 'source-refs.json'),
                '--second-attempt', str(right), '--second-refs', str(right / 'source-refs.json')]
        run(base + ['--output', str(HERE / 'comparisons' / (name + '.original-diagnostic.json')),
                    '--allow-diagnostic', '--expected-frames', '3'],
            HERE / f'cpu-original-comparison-{name}-positive.log', 0, '"production": false')
        run(base + ['--output', str(SCRATCH / (name + '-negative.json'))],
            HERE / f'cpu-original-comparison-{name}-negative.log', 1, 'unreviewed original site rejected')
    root = roots[SUFFIXES[0]]
    video = root / 'overview.mkv'
    bad = root / 'bad-rate.mkv'
    subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-i', str(video),
                    '-r', '10', '-c:v', 'ffv1', '-threads', '1', str(bad)], check=True)
    bad.replace(video)
    seal_path = root / 'capture-seal.json'
    seal = json.loads(seal_path.read_text(encoding='utf-8'))
    seal['sources']['overview.mkv'] = hashlib.sha256(video.read_bytes()).hexdigest()
    seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    run([sys.executable, str(HERE / 'original_attempt_audit.py'),
         '--case', HERE.name + '__' + SUFFIXES[0], '--attempt', str(root),
         '--refs', str(root / 'source-refs.json'), '--output', str(SCRATCH / 'bad-rate-result.json'),
         '--allow-diagnostic', '--expected-frames', '3'],
        HERE / 'cpu-original-audit-changed-media-negative.log', 1,
        'original video codec, rate, dimensions or frame count mismatch')
    altered = roots[SUFFIXES[1]] / 'native-acquisition.json'
    altered.write_bytes(altered.read_bytes() + b'changed')
    run([sys.executable, str(HERE / 'original_attempt_audit.py'),
         '--case', HERE.name + '__' + SUFFIXES[1], '--attempt', str(roots[SUFFIXES[1]]),
         '--refs', str(roots[SUFFIXES[1]] / 'source-refs.json'),
         '--output', str(SCRATCH / 'changed-native-result.json'),
         '--allow-diagnostic', '--expected-frames', '3'],
        HERE / 'cpu-original-audit-changed-source-negative.log', 1, 'saved source hash mismatch')
    print('four original-attempt diagnostic positives, eight production negatives,')
    print('three comparison positives, three comparison production negatives,')
    print('changed-media and changed-Native-source negatives: pass')


if __name__ == '__main__':
    main()
