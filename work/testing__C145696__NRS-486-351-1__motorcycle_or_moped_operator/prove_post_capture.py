"""Exercise selected saved-only processing on retained source-shaped diagnostic captures."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

ASSIGNMENT = 'testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator'
ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work' / ASSIGNMENT
SCRATCH = ROOT / '.runtime-work' / 'c145696' / 'post-capture'
VALIDATOR = ROOT / '.runtime-work' / 'c10307-decoder' / '.lake/build/bin/adapterCheck'
EXCLUDE = {'candidate-selection.json', 'result.json', 'analysis-report.json', 'compatibility.json', 'processing.json', 'feedback.json', 'traffic_spec', 'converted', 'channels', 'event_review.webm', 'event_review.json', 'event_review_encoder.log', 'event_review_frames.jsonl', 'review_label.txt', 'review_measured_speed.ass', 'review_render.lock', 'final-decode.json'}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def sources(case):
    candidates = [ROOT / '.runtime-work/c145696' / f'compat7-{case}', ROOT / '.runtime-work/c145696/compatall' / f'{case}-primary']
    return next(p for p in candidates if p.is_dir())

def make_attempt(case, variant):
    source = sources(case)
    dest = SCRATCH / f'{case}-{variant}-attempt'
    if dest.exists():
        import shutil
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for p in source.iterdir():
        if p.name in EXCLUDE or p.name.startswith(('source-', 'primary', 'annotated')):
            continue
        if p.is_dir():
            if p.name != 'capture' and p.name != 'cameras':
                continue
            for q in p.rglob('*'):
                if q.is_file():
                    target = dest / q.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.link(q, target)
        elif p.is_file():
            os.link(p, dest / p.name)
    if variant == 'missing-source':
        (dest / 'lane-split-history.jsonl').unlink()
    return dest

def run_case(case, variant):
    attempt = make_attempt(case, variant)
    output = SCRATCH / f'{case}-{variant}-output'
    if output.exists():
        import shutil
        shutil.rmtree(output)
    validator = VALIDATOR if variant != 'missing-validator' else SCRATCH / 'absent-adapterCheck'
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved', '--manifest', str(WORK / 'execution-manifest.json'), '--case', f'{ASSIGNMENT}__{case}', '--attempt', str(attempt), '--output', str(output), '--library', str(ROOT / 'runtime/library'), '--validator', str(validator)]
    env = os.environ.copy()
    env.update(PYTHONDONTWRITEBYTECODE='1', SCENARIO_PIPELINE_OUTPUT_ROOT=str(SCRATCH), TMPDIR=str(SCRATCH))
    proc = subprocess.run(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log = WORK / f'cpu-post-capture-{case}-{variant}.log'
    log.write_text(proc.stdout + f'\nexit_code={proc.returncode}\n')
    version = output / 'v0001'
    receipt = json.loads((version / 'processing.json').read_text()) if (version / 'processing.json').is_file() else None
    feedback = json.loads((version / 'feedback.json').read_text()) if (version / 'feedback.json').is_file() else None
    if variant == 'positive':
        assert proc.returncode == 0 and receipt and receipt['recorded_only'] and receipt['originals_preserved'] and not receipt['missing_evidence'], (case, proc.stdout[-1000:])
    elif variant == 'missing-source':
        assert proc.returncode == 0 and receipt and receipt['missing_evidence'] and feedback and feedback['recorded_only'] and not feedback['native_replay_requested'], (case, proc.stdout[-1000:])
    else:
        assert proc.returncode != 0 and feedback and feedback['recorded_only'] and not feedback['native_replay_requested'], (case, proc.stdout[-1000:])
    return {'case_id': f'{ASSIGNMENT}__{case}', 'variant': variant, 'exit_code': proc.returncode, 'log': log.name, 'log_sha256': sha(log), 'feedback_sha256': sha(version / 'feedback.json') if feedback else None, 'processing_sha256': sha(version / 'processing.json') if receipt else None}

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('case'); p.add_argument('variant', choices=['positive', 'missing-source', 'missing-validator']); a = p.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    print(json.dumps(run_case(a.case, a.variant), sort_keys=True))
