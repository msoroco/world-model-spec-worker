"""Bind the current first exact case CPU proof and independent source audit."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__vehicle_left_indicator'
MANIFEST = ROOT / 'vehicle-indicator-manifest.json'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
assert entry['case_id'] == CASE
receipt = json.loads((ROOT / 'vehicle-indicator-compatibility-receipt.json').read_text())
saved = json.loads((ROOT / 'vehicle-indicator-saved-receipt.json').read_text())
audit = json.loads((ROOT / 'vehicle-indicator-audit.json').read_text())
assert receipt['passed'] and receipt['construction_sha256'] == entry['construction_sha256']
assert receipt['negative_removed'] == 'ego_signal_audio.jsonl'
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert audit['source_integrity_passed'] and audit['video_decode_count'] == 4
assert 'Stale or missing original indicator source' in (ROOT / 'vehicle-indicator-stale-audit.log').read_text()
entry['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/{MANIFEST.name} '
                             f'--case {CASE} --output .runtime-work/c111603-vehicle-indicator-offline-b '
                             f'--python {REPO}/.venv-cpu/bin/python',
                    'exit_code': 0, 'log': 'vehicle-indicator-offline.log',
                    'log_sha256': sha(ROOT / 'vehicle-indicator-offline.log'),
                    'construction_sha256': entry['construction_sha256']}
entry['compatibility'] = {'receipt': 'vehicle-indicator-compatibility-receipt.json',
                          'sha256': sha(ROOT / 'vehicle-indicator-compatibility-receipt.json'),
                          'log': 'vehicle-indicator-analysis.log'}
entry['negative'] = {'log': 'vehicle-indicator-negative.log'}
audit_script = ROOT / 'vehicle_indicator_audit.py'
positive = f'.venv-cpu/bin/python work/{ROOT.name}/vehicle_indicator_audit.py --attempt .runtime-work/c111603-vehicle-indicator-compat-d --output work/{ROOT.name}/vehicle-indicator-audit.json'
entry['delivery_acceptance'] = {'case_id': CASE, 'sets': ['held-out'],
    'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
               'actual_pixels', 'physical_completion'],
    'script': 'vehicle_indicator_audit.py', 'script_sha256': sha(audit_script),
    'command': positive + f' --case {CASE}', 'test_exit_code': 0,
    'test_log': 'vehicle-indicator-audit.log',
    'test_log_sha256': sha(ROOT / 'vehicle-indicator-audit.log'),
    'negative_command': positive + f' --case {CASE} --negative',
    'negative_exit_code': 1,
    'negative_expected_error': 'Stale or missing original indicator source',
    'negative_log': 'vehicle-indicator-stale-audit.log',
    'negative_log_sha256': sha(ROOT / 'vehicle-indicator-stale-audit.log')}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('First exact indicator offline, compatibility, saved and audit receipts bound')
