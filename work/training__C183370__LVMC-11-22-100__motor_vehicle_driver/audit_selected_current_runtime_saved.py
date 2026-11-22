"""Independently verify all selected current-runtime saved CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
ASSETS = ROOT / '.runtime-work/c183370-selected-current-saved'
RECEIPTS = HERE / 'selected-current-runtime-saved-receipts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def main():
    manifest = read(MANIFEST)
    manifest_sha = sha(MANIFEST)
    rows = []
    for case in manifest['cases']:
        short = case['case_id'].split('__')[-1]
        for selected in [case, *case['candidates']]:
            candidate = selected.get('id', 'primary')
            base = ASSETS / short / candidate
            returned = RECEIPTS / short / candidate
            proof = read(returned / 'proof.json')
            processing = read(returned / 'processing.json')
            selection = read(base / 'source/candidate-selection.json')
            compatibility_path = HERE / selected['compatibility']['receipt']
            compatibility = read(compatibility_path)
            require(proof['case_id'] == case['case_id'] ==
                    processing['case_id'] == selection['case_id'] ==
                    compatibility['case_id'] and
                    proof['candidate_id'] == candidate ==
                    processing['candidate_id'] == selection['candidate_id'] ==
                    compatibility['candidate_id'],
                    'Selected saved identity differs: ' + short + '/' + candidate)
            require(proof['selected_manifest_sha256'] ==
                    selection['manifest_sha256'] == manifest_sha and
                    proof['runtime_manifest_sha256'] ==
                    compatibility['runtime_manifest_sha256'] ==
                    manifest['runtime_manifest_sha256'] and
                    proof['construction_sha256'] ==
                    selection['construction_sha256'] ==
                    processing['analysis_revision']['construction_sha256'] ==
                    compatibility['construction_sha256'] ==
                    selected['construction_sha256'],
                    'Selected saved runtime or construction differs')
            require(proof['compatibility_receipt_sha256'] ==
                    sha(compatibility_path) == selected['compatibility']['sha256'] and
                    proof['processing_sha256'] == sha(returned / 'processing.json') and
                    proof['selection_sha256'] ==
                    sha(base / 'source/candidate-selection.json'),
                    'Selected saved receipt hash differs')
            require(compatibility['passed'] is True and
                    processing['passed'] is True and
                    processing['recorded_only'] is True and
                    processing['originals_preserved'] is True and
                    processing['missing_evidence'] is False and
                    processing['timestamp_joins']['frames'] == 600 and
                    processing['final_video_checks']['passed'] is True and
                    processing['final_video_checks']['frames'] == 600 and
                    proof['recorded_only_saved_passed'] is True and
                    proof['synthetic_fixture'] is True and
                    proof['original_native_verified'] is False and
                    proof['physical_or_legal_acceptance_claimed'] is False,
                    'Selected saved CPU proof incomplete')
            for name, digest in processing['original_source_hashes'].items():
                require(sha(base / 'source' / name) == digest,
                        'Selected original source changed: ' + name)
            rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                         'proof_sha256': sha(returned / 'proof.json'),
                         'processing_sha256': sha(returned / 'processing.json')})
    require(len(rows) == 48, 'Expected 48 selected candidate proofs')
    out = HERE / 'selected-current-runtime-saved-audit-index.json'
    out.write_text(json.dumps({'format': 'selected-current-runtime-saved-audit-index',
                               'selected_manifest_sha256': manifest_sha,
                               'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
                               'count': len(rows), 'rows': rows,
                               'synthetic_fixture': True,
                               'original_native_verified': False},
                              indent=2, sort_keys=True) + '\n')
    print(json.dumps({'count': len(rows), 'index_sha256': sha(out)},
                     sort_keys=True))


if __name__ == '__main__':
    main()
