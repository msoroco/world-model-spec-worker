"""Retain hash-bound recorded-only results for the fifth case and fallbacks."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / 'mid-speed-compatibility-manifest.json'
CASE = HERE.name + '__yield_nearest_view_mid_speed'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_sha = sha(MANIFEST)
    results = []
    for ident in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        if ident == 'primary':
            saved = REPO / '.runtime-work/c158190-mid-stable-primary-saved-v2/v0001/processing.json'
            compatibility = REPO / '.runtime-work/c158190-mid-stable-primary-compat-v2/compatibility.json'
        else:
            stem = f'c158190-yield_nearest_view_mid_speed-{ident}-stable-v2'
            saved = REPO / '.runtime-work' / (stem + '-saved/v0001/processing.json')
            compatibility = REPO / '.runtime-work' / (stem + '-compat/compatibility.json')
        result = json.loads(saved.read_text())
        proof = json.loads(compatibility.read_text())
        if (result.get('case_id') != CASE or result.get('candidate_id') != ident or
                result.get('passed') is not True or result.get('recorded_only') is not True or
                result.get('originals_preserved') is not True or
                result.get('physical_acceptance_claimed') is not False or
                result.get('legal_acceptance_claimed') is not False or
                proof.get('passed') is not True or proof.get('candidate_id') != ident):
            raise ValueError('Saved or compatibility proof missing for ' + ident)
        results.append({'candidate_id': ident, 'saved_processing_sha256': sha(saved),
                        'compatibility_sha256': sha(compatibility),
                        'recorded_only': True, 'originals_preserved': True,
                        'physical_acceptance_claimed': False,
                        'legal_acceptance_claimed': False})
    receipt = {'format': 'c158190-mid-speed-saved-diagnostic', 'case_id': CASE,
               'manifest_sha256': manifest_sha, 'results': results,
               'selected_delivery_manifest_changed': False}
    target = HERE / 'cases/through_mid/stable-saved-diagnostic.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
