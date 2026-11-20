"""Bind forty same-cell diagnostic chains to their current exact manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PAIRS = {
    'warning_person': 'update126-current-warning-pair-audit.json',
    'barrier': 'update127-current-barrier-pair-audit.json',
    'warning_sign': 'update127-current-warning-sign-pair-audit.json',
    'highway_closed_sign': 'update127-current-highway-sign-pair-audit.json',
    'employee_exception': 'update127-current-employee-pair-audit.json',
}


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = HERE / 'draft-combined-capture-manifest.json'
    manifest, digest = read(manifest_path), sha(manifest_path)
    offline_matrix_path = HERE / 'update125-combined-offline-matrix.json'
    offline_matrix = read(offline_matrix_path)
    assert len(manifest['cases']) == 10
    assert offline_matrix['manifest_sha256'] == digest
    assert offline_matrix['passed'] == offline_matrix['candidates'] == 40
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        assert case.startswith(HERE.name + '__')
        short = case[len(HERE.name) + 2:]
        candidates = [('primary', entry)] + [
            (candidate['id'], candidate) for candidate in entry['candidates']]
        assert [name for name, _ in candidates] == [
            'primary', 'fallback1', 'fallback2', 'fallback3']
        for candidate, selected in candidates:
            construction = HERE / selected['construction']
            assert sha(construction) == selected['construction_sha256']
            offline_path = ROOT / '.runtime-work/c183370-update125-combined-offline-matrix' \
                / short / candidate / 'candidate-selection.json'
            offline = read(offline_path)
            proof_path = HERE / ('update125-combined-' + short + '-' + candidate + '-proof.json')
            proof = read(proof_path)
            base = ROOT / '.runtime-work' / (
                'c183370-update125-combined-' + short + '-' + candidate)
            compat = Path(str(base) + '-compat')
            source = Path(str(base) + '-source')
            saved = Path(str(base) + '-saved/v0001')
            selection = read(compat / 'candidate-selection.json')
            receipt = read(compat / 'compatibility.json')
            processing = read(saved / 'processing.json')
            result = read(saved / 'analysis/result.json')
            for row in (offline, proof, selection, receipt, processing):
                assert row['case_id'] == case and row['candidate_id'] == candidate
            assert offline['manifest_sha256'] == proof['manifest_sha256'] == \
                selection['manifest_sha256'] == \
                read(source / 'candidate-selection.json')['manifest_sha256'] == digest
            assert offline['construction_sha256'] == proof['construction_sha256'] == \
                selection['construction_sha256'] == receipt['construction_sha256'] == \
                processing['analysis_revision']['construction_sha256'] == \
                selected['construction_sha256']
            assert proof['passed'] is True and proof['diagnostic_only'] is True
            assert proof['compatibility_receipt_sha256'] == sha(compat / 'compatibility.json')
            assert proof['saved_receipt_sha256'] == sha(saved / 'processing.json')
            assert receipt['passed'] is True and receipt['negative_removed'] == 'live-readback.json'
            assert processing['passed'] is True and processing['recorded_only'] is True
            assert processing['originals_preserved'] is True and processing['missing_evidence'] is False
            assert processing['timestamp_joins']['passed'] is True
            assert processing['timestamp_joins']['frames'] == 600
            assert processing['final_video_checks']['passed'] is True
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'offline_sha256': sha(offline_path), 'proof_sha256': sha(proof_path),
                         'compatibility_sha256': sha(compat / 'compatibility.json'),
                         'saved_sha256': sha(saved / 'processing.json')})
    assert len(rows) == 40
    pairs = {}
    for name, filename in PAIRS.items():
        path = HERE / filename
        receipt = read(path)
        assert receipt['manifest_sha256'] == digest
        assert receipt['candidate_count'] == 8
        assert receipt['diagnostic_only'] is True
        assert receipt.get('passed', receipt.get('all_passed')) is True
        assert len(receipt['rows']) == 8
        pairs[name] = {'path': filename, 'sha256': sha(path)}
    return {'format': 'c183370-current-forty-candidate-diagnostic-audit-v1',
            'manifest_sha256': digest, 'offline_matrix_sha256': sha(offline_matrix_path),
            'candidate_count': 40, 'passed': True, 'diagnostic_only': True,
            'selected_for_delivery': False, 'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False,
            'pair_audits': pairs, 'rows': rows}


if __name__ == '__main__':
    path = HERE / 'update127-current-forty-candidate-audit.json'
    path.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_count': 40, 'passed': True,
                      'audit_sha256': sha(path)}, sort_keys=True))
