"""Independently verify returned cutover receipts for the first selected pair."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'current-runtime-probe-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(MANIFEST)
    offline = read(HERE / 'current-runtime-offline-index.json')
    if offline['manifest_sha256'] != sha(MANIFEST) or offline['count'] != 48:
        raise ValueError('Offline matrix binding incomplete')
    rows = []
    for short in ('reference', 'contrast'):
        case = next(c for c in manifest['cases'] if c['case_id'] == HERE.name + '__' + short)
        constructions = set()
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected = case if candidate == 'primary' else next(c for c in case['candidates'] if c['id'] == candidate)
            folder = HERE / 'cutover-receipts' / short / candidate
            proof = read(folder / 'proof.json')
            comp, saved = read(folder / 'compatibility.json'), read(folder / 'processing.json')
            if any(sha(folder / name) != digest for name, digest in proof['returned_receipts'].items()):
                raise ValueError('Returned receipt hash mismatch')
            if not (proof['case_id'] == case['case_id'] and proof['candidate_id'] == candidate and
                    proof['manifest_sha256'] == sha(MANIFEST) and
                    proof['construction_sha256'] == selected['construction_sha256'] ==
                    comp['construction_sha256'] == saved['analysis_revision']['construction_sha256']):
                raise ValueError('Case/candidate/manifest/construction binding mismatch')
            if not (comp['passed'] and comp['negative_error_contains'] == 'Missing required source: live-readback.json' and
                    saved['passed'] and saved['recorded_only'] and saved['originals_preserved'] and
                    not saved['missing_evidence'] and saved['timestamp_joins']['frames'] == 600):
                raise ValueError('Positive, negative, or saved path incomplete')
            if proof['original_native_verified'] or proof['physical_or_legal_acceptance_claimed']:
                raise ValueError('Synthetic fixture misrepresented')
            constructions.add(selected['construction_sha256'])
            rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                         'proof_sha256': sha(folder / 'proof.json')})
        if len(constructions) != 4:
            raise ValueError('Candidate constructions are not distinct')
    output = HERE / 'current-runtime-pair-proof-index.json'
    output.write_text(json.dumps({'format': 'current-runtime-pair-cpu-proof-index',
                                  'manifest_sha256': sha(MANIFEST),
                                  'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                                  'offline_index_sha256': sha(HERE / 'current-runtime-offline-index.json'),
                                  'count': len(rows), 'rows': rows,
                                  'synthetic_fixture': True,
                                  'selected_manifest_rebound': False}, indent=2,
                                 sort_keys=True) + '\n')
    print(json.dumps({'count': len(rows), 'index_sha256': sha(output)}))


if __name__ == '__main__':
    main()
