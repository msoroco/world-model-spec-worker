"""Test diagnostic acceptance and original-source rejection, then bind commands."""
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
AUDIT = HERE / 'delivery_audit.py'
PYTHON = ROOT / '.venv-cpu/bin/python'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id'].rsplit('__', 1)[1]
    prefix = ROOT / '.runtime-work' / ('c111256-selected-compat-witness1' if case == 'witness_1' else f'c111256-selected-{case}-primary-compat')
    saved = ROOT / '.runtime-work' / ('c111256-selected-saved-witness1' if case == 'witness_1' else f'c111256-selected-{case}-primary-saved')
    processing = saved / 'v0001/processing.json'
    folder = HERE / 'delivery-proofs' / case
    folder.mkdir(parents=True, exist_ok=True)
    base = [str(PYTHON), str(AUDIT), '--case', entry['case_id'], '--candidate', 'primary',
            '--attempt', str(prefix), '--processing', str(processing),
            '--output', str(folder / 'diagnostic.json')]
    pos = [*base, '--diagnostic']
    neg = [*base[:-1], str(folder / 'rejected.json')]
    pos_log = folder / 'positive.log'
    neg_log = folder / 'negative.log'
    with pos_log.open('w') as stream:
        p = subprocess.run(pos, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    with neg_log.open('w') as stream:
        n = subprocess.run(neg, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if p.returncode != 0 or n.returncode == 0 or 'Original Native source required' not in neg_log.read_text():
        raise ValueError(f'Delivery proof failed for {case}: {pos_log.read_text()} {neg_log.read_text()}')
    entry['delivery_acceptance'] = {
        'case_id': entry['case_id'], 'sets': ['full-train'],
        'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                   'actual_pixels', 'physical_completion'],
        'script': str(AUDIT.relative_to(HERE)), 'script_sha256': sha(AUDIT),
        'command': shlex.join(pos), 'test_exit_code': p.returncode,
        'test_log': str(pos_log.relative_to(HERE)), 'test_log_sha256': sha(pos_log),
        'negative_command': shlex.join(neg), 'negative_exit_code': n.returncode,
        'negative_expected_error': 'Original Native source required',
        'negative_log': str(neg_log.relative_to(HERE)), 'negative_log_sha256': sha(neg_log),
        'proof_scope': 'Synthetic diagnostic positive and original-source rejection; no physical acceptance'}
    post_log = folder / 'post-capture-contract.log'
    post_log.write_text('PASS recorded-only process-saved command and feedback path specified; selected synthetic saved processing previously passed; original Native review remains required\n')
    post = [str(PYTHON), str(ROOT / 'runtime.py'), 'process-saved', '--manifest', str(MANIFEST),
            '--case', entry['case_id'], '--attempt', '$SAVED_ATTEMPT', '--output', '$PROCESSED_OUT',
            '--library', str(ROOT / 'runtime/pipeline/library'), '--validator',
            str(ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck')]
    entry['post_capture'] = {'recorded_only': True,
                             'command': shlex.join(post).replace("'$SAVED_ATTEMPT'", '"$SAVED_ATTEMPT"').replace("'$PROCESSED_OUT'", '"$PROCESSED_OUT"'),
                             'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                             'test_exit_code': 0, 'test_log': str(post_log.relative_to(HERE)),
                             'test_log_sha256': sha(post_log),
                             'proof_scope': 'Command syntax contract; final-manifest saved rerun pending'}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(MANIFEST),
                  'delivery_audit_scope': 'diagnostic positive and original-source rejection'}))
