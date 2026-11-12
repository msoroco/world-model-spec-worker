"""Bind all selected-manifest compatibility and recorded-only replays."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    digest = sha(MANIFEST)
    entries = json.loads(MANIFEST.read_text())['cases']
    rows = []
    for entry in entries:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        version = 'v3' if suffix == 'yield_nearest_view_mid_speed' else 'v2'
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            stem = f'c158190-{suffix}-{candidate}-stable-{version}'
            base = REPO / '.runtime-work'
            receipt = base / f'{stem}-compat/compatibility.json'
            saved = base / f'{stem}-saved/v0001/processing.json'
            a, b = json.loads(receipt.read_text()), json.loads(saved.read_text())
            if (a.get('passed') is not True or a.get('candidate_id') != candidate
                    or b.get('case_id') != case or b.get('candidate_id') != candidate
                    or any(b.get(key) is not True for key in
                           ('passed', 'recorded_only', 'originals_preserved'))
                    or any(b.get(key) is not False for key in
                           ('physical_acceptance_claimed', 'legal_acceptance_claimed'))):
                raise ValueError(f'Incomplete selected saved proof: {case} {candidate}')
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'compatibility': str(receipt.relative_to(REPO)),
                         'compatibility_sha256': sha(receipt),
                         'processing': str(saved.relative_to(REPO)),
                         'processing_sha256': sha(saved)})
    if sha(MANIFEST) != digest:
        raise ValueError('Selected manifest changed during proof summary')
    output = {'format': 'c158190-selected-saved-proof-summary',
              'manifest_sha256': digest, 'candidate_count': len(rows),
              'recorded_only': True, 'physical_acceptance_claimed': False,
              'results': rows}
    path = ROOT / 'selected-saved-proof-summary.json'
    path.write_text(json.dumps(output, indent=2) + '\n')
    print(json.dumps({'candidate_count': len(rows), 'manifest_sha256': digest,
                      'summary_sha256': sha(path)}))


if __name__ == '__main__':
    main()
