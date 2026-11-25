"""Bind independent source/media diagnostic delivery audit proofs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for index, entry in enumerate(manifest['cases']):
    letter = 'a' if index == 0 else 'b'
    case = entry['case_id']
    prefix = f'proofs/condition_{letter}/'
    script = 'native/delivery_audit.py'
    positive = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ROOT.name}/{script} '
                f'--attempt .runtime-work/c111277-compat-new-{letter}-primary '
                f'--case {case} --output work/{ROOT.name}/{prefix}delivery-positive.json')
    negative = (f'PYTHONDONTWRITEBYTECODE=1 .venv-cpu/bin/python work/{ROOT.name}/native/prove_delivery_audit.py '
                f'--letter {letter} --case {case} --mode missing')
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['demo-train', 'full-train'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': script, 'script_sha256': sha(ROOT / script),
        'command': positive, 'test_exit_code': 0,
        'test_log': prefix + 'delivery-positive.log',
        'test_log_sha256': sha(ROOT / (prefix + 'delivery-positive.log')),
        'negative_command': negative, 'negative_exit_code': 3,
        'negative_expected_error': 'missing original: native-rows.jsonl',
        'negative_log': prefix + 'delivery-missing.log',
        'negative_log_sha256': sha(ROOT / (prefix + 'delivery-missing.log')),
        'additional_negative': {'command': negative.replace('--mode missing', '--mode altered'),
                                'exit_code': 3,
                                'expected_error': 'altered original: native-rows.jsonl',
                                'log': prefix + 'delivery-altered.log',
                                'log_sha256': sha(ROOT / (prefix + 'delivery-altered.log'))},
        'diagnostic_fixture_only': True,
        'physical_acceptance_claimed': False}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
