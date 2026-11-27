"""Bind source-hashed three-outcome lane-transition and lifecycle receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        receipt = HERE / 'physical-proof' / suffix / 'proof.json'
        proof = json.loads(receipt.read_text())
        if proof['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Stale physical proof: ' + suffix)
        entry['physical_preparation'] = {'receipt': str(receipt.relative_to(HERE)), 'sha256': sha(receipt)}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
