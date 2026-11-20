"""Audit current selected-manifest CPU diagnostics without claiming delivery acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def paths(short, candidate):
    update = 130 if candidate == 'primary' and short in ('reference', 'contrast') else 131 if candidate == 'primary' else 132
    stem = f'c183370-update{update}-selected-{short}-{candidate}'
    base = ROOT / '.runtime-work' / stem
    offline = Path(str(base) + '-offline')
    if (update, short, candidate) in ((130, 'reference', 'primary'), (132, 'reference', 'fallback1')):
        offline = Path(str(base) + '-offline-v2')
    return update, base, offline


def audit():
    manifest_path = HERE / 'execution-manifest.json'
    manifest, digest = read(manifest_path), sha(manifest_path)
    assert manifest['status'] == 'selected_cpu_preparation_incomplete'
    assert len(manifest['cases']) == 10
    rows = []
    for entry in manifest['cases']:
        case = entry['case_id']
        assert case.startswith(HERE.name + '__')
        short = case[len(HERE.name) + 2:]
        candidates = [('primary', entry)] + [(row['id'], row) for row in entry['candidates']]
        assert [name for name, _ in candidates] == ['primary', 'fallback1', 'fallback2', 'fallback3']
        for candidate, selected in candidates:
            assert sha(HERE / selected['construction']) == selected['construction_sha256']
            update, base, offline = paths(short, candidate)
            source = Path(str(base) + '-source')
            compat = Path(str(base) + '-compat')
            saved = Path(str(base) + '-saved/v0001')
            selections = [read(offline / 'candidate-selection.json'),
                          read(source / 'candidate-selection.json'),
                          read(compat / 'candidate-selection.json')]
            receipt = read(compat / 'compatibility.json')
            processing = read(saved / 'processing.json')
            result = read(saved / 'analysis/result.json')
            diagnostic_path = HERE / f'update{update}-selected-{short}-{candidate}-delivery-diagnostic.json'
            diagnostic = read(diagnostic_path)
            for selection in selections:
                assert (selection['case_id'], selection['candidate_id'],
                        selection['manifest_sha256'], selection['construction_sha256']) == (
                            case, candidate, digest, selected['construction_sha256'])
            assert receipt['case_id'] == case and receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['passed'] is True and receipt['negative_removed'] == 'live-readback.json'
            assert processing['case_id'] == case and processing['candidate_id'] == candidate
            assert processing['analysis_revision']['construction_sha256'] == selected['construction_sha256']
            assert processing['passed'] is True and processing['recorded_only'] is True
            assert processing['originals_preserved'] is True and processing['missing_evidence'] is False
            assert processing['timestamp_joins']['passed'] is True
            assert processing['timestamp_joins']['frames'] == 600
            assert processing['final_video_checks']['passed'] is True
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert diagnostic['case_id'] == case and diagnostic['candidate_id'] == candidate
            assert diagnostic['manifest_sha256'] == digest
            assert diagnostic['accepted'] is False and diagnostic['diagnostic_only'] is True
            assert diagnostic['physical_or_legal_acceptance_claimed'] is False
            rows.append({'case_id': case, 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'offline_sha256': sha(offline / 'candidate-selection.json'),
                         'source_selection_sha256': sha(source / 'candidate-selection.json'),
                         'compatibility_sha256': sha(compat / 'compatibility.json'),
                         'saved_sha256': sha(saved / 'processing.json'),
                         'delivery_diagnostic_sha256': sha(diagnostic_path)})
    assert len(rows) == 40
    pairs = {}
    for name, update in [('main', 130), ('barrier', 131), ('warning_sign', 131),
                         ('highway_closed_sign', 131), ('employee_exception', 131)]:
        path = HERE / f'update{update}-selected-{name}-comparison-diagnostic.json'
        receipt = read(path)
        assert receipt['manifest_sha256'] == digest
        assert receipt['diagnostic_only'] is True and receipt['accepted'] is False
        assert receipt['fixed_context_checked'] is True
        pairs[name] = {'path': path.name, 'sha256': sha(path)}
    return {'format': 'c183370-selected-forty-candidate-cpu-diagnostic-audit-v1',
            'manifest_sha256': digest, 'candidate_count': 40, 'passed': True,
            'diagnostic_only': True, 'final_manifest_proof': False,
            'original_native_observed': False,
            'physical_or_legal_acceptance_claimed': False,
            'pair_diagnostics': pairs, 'rows': rows}


if __name__ == '__main__':
    path = HERE / 'update132-selected-forty-candidate-audit.json'
    path.write_text(json.dumps(audit(), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'candidate_count': 40, 'passed': True, 'audit_sha256': sha(path)}, sort_keys=True))
