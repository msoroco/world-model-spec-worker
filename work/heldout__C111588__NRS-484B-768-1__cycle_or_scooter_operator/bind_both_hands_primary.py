"""Retain exact both-hands primary CPU proof and audit receipts."""
from hashlib import sha256
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
FOLDER = ROOT / 'cases/both_hands_no_signal'
MANIFEST = ROOT / 'both-hands-manifest.json'


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


sources = {
    'offline_log': REPO / '.runtime-work/c111588-both-hands-primary-offline-b/offline.log',
    'compatibility_receipt': REPO / '.runtime-work/c111588-both-hands-primary-compat-b/compatibility.json',
    'compatibility_analysis_log': REPO / '.runtime-work/c111588-both-hands-primary-compat-b/compatibility-analysis.log',
    'compatibility_negative_log': REPO / '.runtime-work/c111588-both-hands-primary-compat-b/negative-analysis.log',
    'saved_receipt': REPO / '.runtime-work/c111588-both-hands-saved-b/v0001/processing.json',
    'saved_analysis_log': REPO / '.runtime-work/c111588-both-hands-saved-b/v0001/analysis.log',
}
files = {}
for label, source in sources.items():
    target = FOLDER / ('proof-' + label.replace('_', '-') + source.suffix)
    shutil.copy2(source, target)
    files[label] = {'file': target.name, 'sha256': sha(target)}
receipt = json.loads((FOLDER / files['compatibility_receipt']['file']).read_text())
saved = json.loads((FOLDER / files['saved_receipt']['file']).read_text())
entry = json.loads(MANIFEST.read_text())['cases'][0]
assert receipt['passed'] and receipt['construction_sha256'] == entry['construction_sha256']
assert receipt['negative_removed'] == 'hand_contact_readback.jsonl'
assert saved['passed'] and saved['originals_preserved'] and not saved['missing_evidence']
assert not saved['physical_acceptance_claimed'] and not saved['legal_acceptance_claimed']
observation = receipt['measurement_examples']['both_hands_observation']['value']
assert observation['both_hands_required_for_safety'] is None
proof = {'format': 'worker-rider-both-hands-primary-proof', 'case_id': entry['case_id'],
         'construction_sha256': entry['construction_sha256'],
         'manifest_sha256': sha(MANIFEST),
         'measurement_contract_sha256': sha(FOLDER / 'measurement-contract.json'),
         'fixture_recipe_sha256': sha(FOLDER / 'diagnostic-recipe.json'),
         'files': files, 'offline_passed': True, 'compatibility_passed': True,
         'missing_hand_original_rejected': True, 'saved_processing_passed': True,
         'originals_preserved': True,
         'fallbacks': [c['id'] for c in entry['candidates']],
         'independent_audit': entry['physical_preparation'],
         'both_hands_required_for_safety': None,
         'legal_signal_exception_judgment': None,
         'diagnostic_fixture_only': True}
(FOLDER / 'proof.json').write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
print('both-hands primary proof bound; safety necessity unverified')
