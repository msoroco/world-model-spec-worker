"""Bind recorded-only saved and diagnostic delivery CPU receipts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_log(path, data):
    lines = [line.rstrip() for line in data.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('\n'.join(lines) + '\n' if lines else '')


manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
script = HERE / 'delivery_audit.py'
for entry in manifest['cases']:
    case = entry['case_id']
    suffix = case[len(HERE.name) + 2:]
    if suffix not in ('designated', 'opposite'):
        raise ValueError('Unexpected exact case')
    attempt = SCRATCH / f'c150916-saved-attempt-{suffix}'
    processing = SCRATCH / f'c150916-saved-output-{suffix}/v0001/processing.json'
    receipt = json.loads(processing.read_text())
    if receipt['case_id'] != case or receipt['passed'] is not True:
        raise ValueError('Saved processing did not pass')
    proof = HERE / 'proofs' / suffix
    proof.mkdir(parents=True, exist_ok=True)
    copy = proof / 'processing.json'
    shutil.copyfile(processing, copy)
    saved_log = proof / 'saved.log'
    clean_log(saved_log, (SCRATCH / f'c150916-process-saved-{suffix}.log').read_text())
    command = f'{sys.executable} {REPO / "runtime.py"} process-saved --manifest {manifest_path} --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library {REPO / "runtime/library"}'
    entry['post_capture'] = {
        'command': command, 'feedback_command': command, 'recorded_only': True,
        'test_exit_code': 0, 'test_log': str(saved_log.relative_to(HERE)),
        'test_log_sha256': sha(saved_log),
        'processing_receipt': str(copy.relative_to(HERE)),
        'processing_receipt_sha256': sha(copy)
    }
    physical = HERE / 'physical' / suffix / 'complete_motion.json'
    positive_output = proof / 'delivery-positive.json'
    positive = [sys.executable, str(script), '--case', case, '--attempt', str(attempt),
                '--processing', str(copy), '--physical', str(physical), '--output', str(positive_output)]
    good = subprocess.run(positive, capture_output=True, text=True)
    positive_log = proof / 'delivery-positive.log'
    clean_log(positive_log, good.stdout + good.stderr)
    if good.returncode:
        raise ValueError('Positive delivery audit failed: ' + suffix + ': ' + good.stderr[-1000:])
    negative_attempt = SCRATCH / f'c150916-negative-attempt-{suffix}'
    if negative_attempt.exists():
        shutil.rmtree(negative_attempt)
    shutil.copytree(attempt, negative_attempt)
    (negative_attempt / 'vehicle-pose.jsonl').unlink()
    negative_output = proof / 'delivery-negative.json'
    negative = [sys.executable, str(script), '--case', case, '--attempt', str(negative_attempt),
                '--processing', str(copy), '--physical', str(physical), '--output', str(negative_output)]
    bad = subprocess.run(negative, capture_output=True, text=True)
    negative_log = proof / 'delivery-negative.log'
    clean_log(negative_log, bad.stdout + bad.stderr)
    expected = 'Missing required source: vehicle-pose.jsonl'
    if bad.returncode == 0 or expected not in negative_log.read_text():
        raise ValueError('Negative delivery audit did not reject missing pose: ' + suffix)
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['demo-train', 'full-train'],
        'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                   'actual_pixels', 'physical_completion'],
        'script': str(script.relative_to(HERE)), 'script_sha256': sha(script),
        'command': ' '.join(positive), 'test_exit_code': 0,
        'test_log': str(positive_log.relative_to(HERE)), 'test_log_sha256': sha(positive_log),
        'negative_command': ' '.join(negative), 'negative_exit_code': bad.returncode,
        'negative_expected_error': expected, 'negative_log': str(negative_log.relative_to(HERE)),
        'negative_log_sha256': sha(negative_log),
        'scope': 'diagnostic synthetic source and physical checks; actual capture acceptance pending'
    }
    print(suffix, 'saved and delivery positive/negative passed')
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
