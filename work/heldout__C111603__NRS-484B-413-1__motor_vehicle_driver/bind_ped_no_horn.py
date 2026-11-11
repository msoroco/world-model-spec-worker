"""Bind the current narrow case CPU receipts and independent comparison audit."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__ped_no_horn_audio'
MANIFEST = ROOT / 'ped-no-horn-manifest.json'
SOURCE = REPO / '.runtime-work/c111603-ped-no-horn-primary-compat-a'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
entry = manifest['cases'][0]
assert entry['case_id'] == CASE
for source, destination in (
    ('compatibility.json', 'ped-no-horn-compatibility-receipt.json'),
    ('compatibility-analysis.log', 'ped-no-horn-analysis.log'),
    ('negative-analysis.log', 'ped-no-horn-negative.log'),
):
    shutil.copy2(SOURCE / source, ROOT / destination)
receipt = json.loads((ROOT / 'ped-no-horn-compatibility-receipt.json').read_text())
saved = json.loads((ROOT / 'ped-no-horn-saved-receipt.json').read_text())
audit = json.loads((ROOT / 'ped-no-horn-audit.json').read_text())
assert receipt['passed'] and receipt['construction_sha256'] == entry['construction_sha256']
assert receipt['negative_removed'] == 'listener_audio_original.jsonl'
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert audit['source_integrity_passed'] and audit['listener_packets_joined'] > 0 and audit['video_decode_count'] == 4
assert 'Stale or missing original pedestrian listener source' in (ROOT / 'ped-no-horn-stale-audit.log').read_text()
entry['offline'] = {
    'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/{MANIFEST.name} '
               f'--case {CASE} --output .runtime-work/c111603-ped-no-horn-primary-offline-a '
               f'--python {REPO}/.venv-cpu/bin/python',
    'exit_code': 0, 'log': 'ped-no-horn-offline.log',
    'log_sha256': sha(ROOT / 'ped-no-horn-offline.log'),
    'construction_sha256': entry['construction_sha256']}
entry['compatibility'] = {
    'receipt': 'ped-no-horn-compatibility-receipt.json',
    'sha256': sha(ROOT / 'ped-no-horn-compatibility-receipt.json'),
    'log': 'ped-no-horn-analysis.log'}
entry['negative'] = {'log': 'ped-no-horn-negative.log'}
positive = f'.venv-cpu/bin/python work/{ROOT.name}/ped_no_horn_audit.py --case {CASE} '
positive += '--attempt .runtime-work/c111603-ped-no-horn-primary-compat-a '
positive += f'--output work/{ROOT.name}/ped-no-horn-audit.json'
entry['delivery_acceptance'] = {
    'case_id': CASE, 'sets': ['held-out'],
    'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
               'actual_pixels', 'physical_completion'],
    'script': 'ped_no_horn_audit.py',
    'script_sha256': sha(ROOT / 'ped_no_horn_audit.py'),
    'command': positive, 'test_exit_code': 0,
    'test_log': 'ped-no-horn-audit.log',
    'test_log_sha256': sha(ROOT / 'ped-no-horn-audit.log'),
    'negative_command': positive + ' --negative', 'negative_exit_code': 1,
    'negative_expected_error': 'Stale or missing original pedestrian listener source',
    'negative_log': 'ped-no-horn-stale-audit.log',
    'negative_log_sha256': sha(ROOT / 'ped-no-horn-stale-audit.log')}
MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
print('Exact pedestrian no-horn primary, fallbacks, saved and audit receipts bound')
