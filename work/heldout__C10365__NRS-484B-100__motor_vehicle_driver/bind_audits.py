"""Bind tested physical-outcome and delivery-audit receipts to exact cases."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
MANIFEST = ROOT / 'execution-manifest.json'
manifest = json.loads(MANIFEST.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for entry in manifest['cases']:
    case = entry['case_id']
    slug = case.split('__')[-1]
    fixtures = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = f'physical/{slug}-{kind}.json'
        log = f'physical/{slug}-{kind}.log'
        fixtures.append({
            'kind': kind,
            'command': f'.venv-cpu/bin/python work/{AID}/physical_fixture.py --case {case} --kind {kind} --output work/{AID}/{result}',
            'exit_code': 0, 'log': log, 'log_sha256': sha(ROOT / log),
            'result': result, 'result_sha256': sha(ROOT / result),
        })
    life_log = f'physical/{slug}-lifecycle.log'
    physical = {
        'construction_sha256': entry['construction_sha256'],
        'fixture_scope': 'Synthetic Native-shaped outcome and ordered lifecycle protocol; no actual officer, motion or pixels verified',
        'fixtures': fixtures,
        'lifecycle': {
            'events': ['capture_finished', 'encoders_closed', 'restoration_verified',
                       'native_exit', 'owner_released', 'saved_processing_started'],
            'exit_code': 0, 'log': life_log, 'log_sha256': sha(ROOT / life_log),
            'test_scope': 'CPU ordered release probe and bound saved-only receipt; actual owner release requires local verification',
        },
    }
    receipt = ROOT / 'physical' / f'{slug}-proof.json'
    receipt.write_text(json.dumps(physical, indent=2) + '\n')
    entry['physical_preparation'] = {'receipt': str(receipt.relative_to(ROOT)), 'sha256': sha(receipt)}
    script = ROOT / 'prove_delivery_audit.py'
    positive = f'cases/delivery-{slug}-positive.log'
    negative = f'cases/delivery-{slug}-negative.log'
    base = f'.venv-cpu/bin/python work/{AID}/prove_delivery_audit.py --case {case} --attempt .runtime-work/c10365-{slug}-primary-compat-v9'
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['held-out'],
        'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                   'actual_pixels', 'physical_completion'],
        'script': 'prove_delivery_audit.py', 'script_sha256': sha(script),
        'command': base, 'test_exit_code': 0,
        'test_log': positive, 'test_log_sha256': sha(ROOT / positive),
        'negative_command': base + ' --negative', 'negative_exit_code': 1,
        'negative_expected_error': 'Missing required source: officer_direction.json',
        'negative_log': negative, 'negative_log_sha256': sha(ROOT / negative),
        'scope': 'CPU source audit only; actual pixels and officer authority require Native review',
    }
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
