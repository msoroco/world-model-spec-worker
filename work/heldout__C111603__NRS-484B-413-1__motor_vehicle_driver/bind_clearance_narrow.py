"""Bind the current narrow case CPU receipts and independent comparison audit."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__clearance_narrow'
MANIFEST = ROOT / 'clearance-narrow-manifest.json'
SOURCE = REPO / '.runtime-work/c111603-clearance-narrow-primary-compat-c'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
assert entry['case_id'] == CASE
for source, destination in (
    ('compatibility.json', 'clearance-narrow-compatibility-receipt.json'),
    ('compatibility-analysis.log', 'clearance-narrow-analysis.log'),
    ('negative-analysis.log', 'clearance-narrow-negative.log'),
):
    shutil.copy2(SOURCE / source, ROOT / destination)
receipt = json.loads((ROOT / 'clearance-narrow-compatibility-receipt.json').read_text())
saved = json.loads((ROOT / 'clearance-narrow-saved-receipt.json').read_text())
audit = json.loads((ROOT / 'clearance-narrow-audit.json').read_text())
assert receipt['passed'] and receipt['construction_sha256'] == entry['construction_sha256']
assert receipt['negative_removed'] == 'ego_signal_audio.jsonl'
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert audit['source_integrity_passed'] and audit['controlled_pair_passed'] and audit['video_decode_count'] == 4
assert 'Stale or missing original clearance source' in (ROOT / 'clearance-narrow-stale-audit.log').read_text()
entry['offline'] = {
    'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/{MANIFEST.name} '
               f'--case {CASE} --output .runtime-work/c111603-clearance-narrow-primary-offline-b '
               f'--python {REPO}/.venv-cpu/bin/python',
    'exit_code': 0, 'log': 'clearance-narrow-offline.log',
    'log_sha256': sha(ROOT / 'clearance-narrow-offline.log'),
    'construction_sha256': entry['construction_sha256']}
entry['compatibility'] = {
    'receipt': 'clearance-narrow-compatibility-receipt.json',
    'sha256': sha(ROOT / 'clearance-narrow-compatibility-receipt.json'),
    'log': 'clearance-narrow-analysis.log'}
entry['negative'] = {'log': 'clearance-narrow-negative.log'}
positive = f'.venv-cpu/bin/python work/{ROOT.name}/clearance_narrow_audit.py --case {CASE} '
positive += '--attempt .runtime-work/c111603-clearance-narrow-primary-compat-c '
positive += '--baseline .runtime-work/c111603-vehicle-indicator-compat-d '
positive += f'--output work/{ROOT.name}/clearance-narrow-audit.json'
entry['delivery_acceptance'] = {
    'case_id': CASE, 'sets': ['held-out'],
    'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
               'actual_pixels', 'physical_completion'],
    'script': 'clearance_narrow_audit.py',
    'script_sha256': sha(ROOT / 'clearance_narrow_audit.py'),
    'command': positive, 'test_exit_code': 0,
    'test_log': 'clearance-narrow-audit.log',
    'test_log_sha256': sha(ROOT / 'clearance-narrow-audit.log'),
    'negative_command': positive + ' --negative', 'negative_exit_code': 1,
    'negative_expected_error': 'Stale or missing original clearance source',
    'negative_log': 'clearance-narrow-stale-audit.log',
    'negative_log_sha256': sha(ROOT / 'clearance-narrow-stale-audit.log')}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Exact narrow clearance primary, fallbacks, saved and audit receipts bound')
