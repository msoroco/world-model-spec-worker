"""Bind three-outcome physical and lifecycle software fixture proofs."""
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent.parent
manifest_path = folder / 'draft-execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].rsplit('__', 1)[-1]
    path = folder / 'proofs' / suffix / 'physical-preparation.json'
    proof = json.loads(path.read_text())
    if proof['case_id'] != entry['case_id'] or proof['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Physical software proof binds another construction')
    entry['physical_preparation'] = {'receipt': str(path.relative_to(folder)),
                                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
print(json.dumps({'physical_software_proofs_bound': len(manifest['cases'])}))
