"""Exercise exact selected positive and missing-source delivery audit paths."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = REPO / '.runtime-work' / 'c111071-delivery-audit-v2'
OUT.mkdir(parents=True, exist_ok=True)
MANIFEST = json.loads((ROOT / 'execution-manifest.json').read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


proofs = []
for entry in MANIFEST['cases']:
    case = entry['case_id']
    suffix = case.rsplit('__', 1)[-1]
    saved = json.loads((ROOT / 'selected-native' / suffix / 'saved-proof.json').read_text())
    receipt = saved['processing_receipt']
    processing = Path(receipt['version']) / 'processing.json'
    attempt = Path(receipt['version']).parents[1] / 'attempt'
    positive_output = OUT / (suffix + '-positive.json')
    positive = [sys.executable, str(ROOT / 'delivery_audit.py'), '--case', case,
                '--candidate', 'primary', '--attempt', str(attempt),
                '--processing', str(processing), '--output', str(positive_output), '--diagnostic']
    run = subprocess.run(positive, text=True, capture_output=True)
    positive_log = ROOT / 'selected-native' / suffix / 'delivery-positive.log'
    positive_log.write_text((run.stdout + run.stderr).rstrip() + '\n')
    if run.returncode != 0:
        raise ValueError('Positive audit failed: ' + suffix + ': ' + run.stderr)
    value = json.loads(positive_output.read_text())
    if value.get('accepted') or not value.get('diagnostic_only') or not value['checks']['time_join']:
        raise ValueError('Diagnostic audit made an acceptance claim')

    negative_attempt = OUT / (suffix + '-missing-road')
    negative_attempt.mkdir(exist_ok=True)
    for source in ('candidate-selection.json', 'capture/manifest.json', 'native_samples.jsonl',
                   'video_frames.jsonl', 'trace.jsonl',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv'):
        target = negative_attempt / source
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.symlink_to((attempt / source).resolve())
    negative_output = OUT / (suffix + '-negative.json')
    negative = [sys.executable, str(ROOT / 'delivery_audit.py'), '--case', case,
                '--candidate', 'primary', '--attempt', str(negative_attempt),
                '--processing', str(processing), '--output', str(negative_output), '--diagnostic']
    run = subprocess.run(negative, text=True, capture_output=True)
    negative_log = ROOT / 'selected-native' / suffix / 'delivery-negative.log'
    negative_log.write_text((run.stdout + run.stderr).rstrip() + '\n')
    expected = 'Missing original source: road_geometry.json'
    if run.returncode == 0 or expected not in negative_log.read_text():
        raise ValueError('Missing-road negative did not reject: ' + suffix)
    proofs.append({
        'case_id': case, 'script': 'delivery_audit.py', 'script_sha256': sha(ROOT / 'delivery_audit.py'),
        'command': ' '.join(positive), 'test_exit_code': 0,
        'test_log': str(positive_log.relative_to(ROOT)), 'test_log_sha256': sha(positive_log),
        'negative_command': ' '.join(negative), 'negative_exit_code': run.returncode,
        'negative_expected_error': expected,
        'negative_log': str(negative_log.relative_to(ROOT)), 'negative_log_sha256': sha(negative_log),
        'diagnostic_receipt_sha256': sha(positive_output),
    })

proof_path = ROOT / 'selected-delivery-audit-proof.json'
proof_path.write_text(json.dumps({'format': 'c111071-selected-delivery-audit-cpu-v1',
                                  'passed': True, 'diagnostic_only': True,
                                  'original_native_observed': False,
                                  'cases': proofs}, indent=2) + '\n')
print(json.dumps({'cases': len(proofs), 'proof_sha256': sha(proof_path)}))
