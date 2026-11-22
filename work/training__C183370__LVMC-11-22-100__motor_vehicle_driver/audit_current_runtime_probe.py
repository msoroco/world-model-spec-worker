"""Bind the isolated cutover reference primary to retained CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / '.runtime-work/c183370-cutover-probe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    manifest_path = HERE / 'current-runtime-probe-manifest.json'
    manifest = read(manifest_path)
    case = manifest['cases'][0]
    selection_path = BASE / 'source/candidate-selection.json'
    compat_path = BASE / 'compat/compatibility.json'
    saved_path = BASE / 'saved2/v0001/processing.json'
    selection, compat, saved = map(read, (selection_path, compat_path, saved_path))
    expected = case['construction_sha256']
    if selection['manifest_sha256'] != sha(manifest_path):
        raise ValueError('Selection is not bound to current probe manifest')
    if not (selection['construction_sha256'] == compat['construction_sha256'] ==
            saved['analysis_revision']['construction_sha256'] == expected):
        raise ValueError('Exact construction binding differs')
    if not (compat['passed'] and saved['passed'] and saved['recorded_only'] and
            saved['originals_preserved'] and not saved['missing_evidence']):
        raise ValueError('Positive or saved path incomplete')
    if compat['negative_error_contains'] != 'Missing required source: live-readback.json':
        raise ValueError('Missing-source negative was not checked')
    if saved['timestamp_joins']['frames'] != 600:
        raise ValueError('Full 30-second source trace was not joined')
    matrix = read(HERE / 'current-runtime-offline-index.json')
    if matrix['manifest_sha256'] != sha(manifest_path) or matrix['count'] != 48:
        raise ValueError('Offline matrix is incomplete or stale')
    proof = {'format': 'isolated-current-runtime-cpu-proof',
             'status': 'probe_only_selected_manifest_unchanged',
             'case_id': case['case_id'], 'candidate_id': 'primary',
             'manifest_sha256': sha(manifest_path),
             'runtime_manifest_sha256': manifest['runtime_manifest_sha256'],
             'construction_sha256': expected,
             'offline_matrix_sha256': sha(HERE / 'current-runtime-offline-index.json'),
             'compatibility_sha256': sha(compat_path),
             'saved_processing_sha256': sha(saved_path),
             'selection_sha256': sha(selection_path),
             'positive_compatibility_passed': True,
             'missing_source_negative_passed': True,
             'recorded_only_saved_passed': True,
             'source_frames': 600, 'synthetic_fixture': True,
             'original_native_verified': False,
             'physical_or_legal_acceptance_claimed': False}
    out = HERE / 'current-runtime-reference-primary-proof.json'
    out.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(out), 'offline_candidates': matrix['count']}))


if __name__ == '__main__':
    main()
