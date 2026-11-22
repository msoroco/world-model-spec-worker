"""Audit every complete four-candidate cutover case in returned work files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / 'current-runtime-probe-manifest.json'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest = read(MANIFEST)
    offline = read(HERE / 'current-runtime-offline-index.json')
    if offline['manifest_sha256'] != sha(MANIFEST) or offline['count'] != 48:
        raise ValueError('Current-runtime offline matrix is incomplete')
    rows, complete_cases = [], []
    for case in manifest['cases']:
        short = case['case_id'].removeprefix(HERE.name + '__')
        folders = [HERE / 'cutover-receipts' / short / candidate for candidate in CANDIDATES]
        if not any((folder / 'proof.json').is_file() for folder in folders):
            continue
        if not all((folder / 'proof.json').is_file() for folder in folders):
            raise ValueError('Case has incomplete candidate set: ' + short)
        constructions = set()
        for candidate, folder in zip(CANDIDATES, folders):
            selected = case if candidate == 'primary' else next(c for c in case['candidates'] if c['id'] == candidate)
            proof = read(folder / 'proof.json')
            compat, saved = read(folder / 'compatibility.json'), read(folder / 'processing.json')
            if any(sha(folder / name) != checksum for name, checksum in proof['returned_receipts'].items()):
                raise ValueError('Returned receipt hash mismatch: ' + short + '/' + candidate)
            if not (proof['case_id'] == case['case_id'] and proof['candidate_id'] == candidate and
                    proof['manifest_sha256'] == sha(MANIFEST) and
                    proof['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'] and
                    proof['construction_sha256'] == compat['construction_sha256'] ==
                    saved['analysis_revision']['construction_sha256'] == selected['construction_sha256']):
                raise ValueError('Exact identity binding mismatch: ' + short + '/' + candidate)
            if not (compat['passed'] and compat['negative_error_contains'] == 'Missing required source: live-readback.json' and
                    saved['passed'] and saved['recorded_only'] and saved['originals_preserved'] and
                    not saved['missing_evidence'] and saved['timestamp_joins']['frames'] == 600):
                raise ValueError('CPU chain incomplete: ' + short + '/' + candidate)
            if not proof['synthetic_fixture'] or proof['original_native_verified'] or proof['physical_or_legal_acceptance_claimed']:
                raise ValueError('Synthetic proof misrepresented')
            constructions.add(selected['construction_sha256'])
            rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                         'proof_sha256': sha(folder / 'proof.json')})
        if len(constructions) != 4:
            raise ValueError('Fallback constructions not distinct: ' + short)
        complete_cases.append(short)
    index = HERE / 'current-runtime-chain-audit-index.json'
    index.write_text(json.dumps({'format': 'current-runtime-chain-audit-index',
                                 'manifest_sha256': sha(MANIFEST),
                                 'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                                 'offline_index_sha256': sha(HERE / 'current-runtime-offline-index.json'),
                                 'complete_cases': complete_cases,
                                 'candidate_count': len(rows), 'rows': rows,
                                 'selected_manifest_rebound': False,
                                 'synthetic_fixture': True}, indent=2,
                                sort_keys=True) + '\n')
    print(json.dumps({'complete_cases': complete_cases, 'candidate_count': len(rows),
                      'index_sha256': sha(index)}))


if __name__ == '__main__':
    main()
