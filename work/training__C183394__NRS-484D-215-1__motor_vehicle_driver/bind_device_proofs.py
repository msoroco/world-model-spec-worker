"""Bind completed compatibility, physical and audit proofs to visibility manifest entries."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
PROBES = ('device_dim', 'device_high')
MANIFEST = ROOT/'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for probe in PROBES:
    entry = next(e for e in manifest['cases'] if e['case_id'] == AID+'__'+probe)
    physical = ROOT/'native'/f'physical-{probe}-receipt.json'
    audit = ROOT/'native'/f'delivery-{probe}-receipt.json'
    if not entry.get('compatibility') or not entry['candidates'][0].get('compatibility'):
        raise ValueError('Bind only after both public compatibility receipts')
    entry['physical_preparation'] = {'receipt': str(physical.relative_to(ROOT)), 'sha256': sha(physical)}
    entry['delivery_acceptance'] = json.loads(audit.read_text())
    entry['negative'] = {'log': entry['compatibility']['negative_log']}
    case = entry['case_id']
    entry['post_capture'] = {'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{AID}/execution-manifest.json --case {case} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
        'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
        'test_scope': 'Public source-shaped diagnostic saved-only processing; no Native or optical acceptance'}
MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False)+'\n')
print('PASS: four compatibility, two physical and two audit contracts bound')
