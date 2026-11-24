"""Exercise positive diagnostic and negative real-delivery audit paths."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(probe):
    case = HERE.name + '__' + probe
    attempt = ROOT / '.runtime-work/c10389-v3-current-compat' / f'{probe}-primary'
    processing = HERE / 'current-v3-saved-proof' / f'{probe}-primary' / 'processing.json'
    output = HERE / 'delivery-proofs' / probe / 'diagnostic.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)
    base = [sys.executable, str(HERE / 'delivery_audit.py'), '--case', case,
            '--candidate', 'primary', '--attempt', str(attempt),
            '--processing', str(processing), '--output', str(output)]
    positive = subprocess.run(base + ['--diagnostic'], cwd=ROOT, capture_output=True, text=True)
    if positive.returncode:
        raise ValueError(positive.stderr)
    positive_log = output.parent / 'diagnostic.log'
    positive_log.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
    negative = subprocess.run(base, cwd=ROOT, capture_output=True, text=True)
    if negative.returncode == 0 or 'Original Native source required' not in negative.stderr:
        raise ValueError('Synthetic source was not rejected as delivery')
    negative_log = output.parent / 'native-required.log'
    negative_log.write_text(negative.stderr.rstrip() + '\n')
    receipt = {'case_id': case, 'sets': ['full-train'],
               'checks': ['native_source', 'all_participants', 'time_join',
                          'full_video_decode', 'actual_pixels', 'physical_completion'],
               'command': ' '.join(base + ['--diagnostic']),
               'negative_command': ' '.join(base),
               'test_exit_code': 0, 'negative_exit_code': negative.returncode,
               'negative_expected_error': 'Original Native source required',
               'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
               'test_log': str(positive_log.relative_to(HERE)),
               'test_log_sha256': sha(positive_log),
               'negative_log': str(negative_log.relative_to(HERE)),
               'negative_log_sha256': sha(negative_log),
               'diagnostic_result': str(output.relative_to(HERE)),
               'diagnostic_result_sha256': sha(output)}
    print(probe, receipt['diagnostic_result_sha256'])
    return receipt


manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    probe = entry['case_id'].rsplit('__', 1)[1]
    entry['delivery_acceptance'] = build(probe)
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
print('manifest', sha(manifest_path))
