"""Independently verify final-manifest selected offline, compatibility and saved receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
            'derived_outputs_rebuilt', 'four_camera_sources',
            'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


manifest_path = HERE / 'execution-manifest.json'
manifest = read(manifest_path)
summary = read(HERE / 'final-matrix-summary.json')
matrix = {(row['case'], row['candidate']): row for row in summary['results']}
checked = []
for entry in manifest['cases']:
    case = entry['case_id'].rsplit('__', 1)[1]
    post = entry['post_capture']
    assert post['recorded_only'] and 'process-saved' in post['command']
    assert entry['case_id'] in post['command'] and '$SAVED_ATTEMPT' in post['command']
    assert post['feedback_command'] and sha(HERE / post['test_log']) == post['test_log_sha256']
    acceptance = entry['delivery_acceptance']
    assert sha(HERE / acceptance['test_log']) == acceptance['test_log_sha256']
    assert sha(HERE / acceptance['negative_log']) == acceptance['negative_log_sha256']
    assert read(HERE / 'delivery-proofs' / case / 'diagnostic.json')['accepted'] is False
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        row = matrix[(case, candidate)]
        assert row['passed']
        selected = entry if candidate == 'primary' else next(x for x in entry['candidates'] if x['id'] == candidate)
        stem = ROOT / '.runtime-work' / f'c111256-final2-{case}-{candidate}'
        offline = Path(str(stem) + '-offline')
        compat = Path(str(stem) + '-compat')
        saved = Path(str(stem) + '-saved') / 'v0001/processing.json'
        selection = read(compat / 'candidate-selection.json')
        proof = read(compat / 'compatibility.json')
        processing = read(saved)
        assert selection['manifest_sha256'] == sha(manifest_path)
        assert selection['case_id'] == entry['case_id'] and selection['candidate_id'] == candidate
        assert selection['construction_sha256'] == selected['construction_sha256']
        assert proof['passed'] and proof['candidate_id'] == candidate and proof['case_id'] == entry['case_id']
        assert proof['construction_sha256'] == selected['construction_sha256']
        assert REQUIRED <= set(proof['checks']) and proof['negative_removed'] == 'road_geometry.json'
        assert processing['passed'] and processing['recorded_only'] and processing['originals_preserved']
        assert processing['case_id'] == entry['case_id'] and processing['candidate_id'] == candidate
        assert processing['original_source_hashes']['candidate-selection.json'] == sha(compat / 'candidate-selection.json')
        assert processing['timestamp_joins']['frames'] == 480 and processing['final_video_checks']['passed']
        assert not processing['missing_evidence'] and not processing['physical_acceptance_claimed']
        assert not processing['legal_acceptance_claimed']
        assert sha(offline / 'offline.log') == row['offline_log_sha256']
        assert sha(compat / 'compatibility.json') == row['compatibility_receipt_sha256']
        assert sha(saved) == row['saved_receipt_sha256']
        checked.append({'case': case, 'candidate': candidate,
                        'construction_sha256': selected['construction_sha256'],
                        'candidate_selection_sha256': sha(compat / 'candidate-selection.json'),
                        'saved_receipt_sha256': sha(saved)})
assert len(checked) == len(matrix) == 16
comparisons = read(HERE / 'comparison-audit-specs.json')['comparisons']
assert len(comparisons) == 2
for comparison in comparisons:
    assert sha(HERE / comparison['diagnostic_log']) == comparison['diagnostic_log_sha256']
    assert sha(HERE / comparison['negative_log']) == comparison['negative_log_sha256']
    assert read(HERE / comparison['diagnostic_receipt'])['accepted'] is False
dispatch = read(HERE / 'dispatch-commands.json')
assert dispatch['manifest_sha256'] == sha(manifest_path)
assert len(dispatch['cases']) == 4 and len(dispatch['comparison_audit_commands']) == 2
result = {'format': 'c111256-final-manifest-matrix-audit', 'passed': True,
          'manifest_sha256': sha(manifest_path), 'selected_candidate_count': 16,
          'saved_count': 16, 'negative_count': 16,
          'delivery_diagnostic_count': 4, 'comparison_diagnostic_count': 2,
          'scope': 'Synthetic CPU diagnostics only; original Native/physical/legal acceptance unverified',
          'checked': checked}
(HERE / 'final-matrix-audit.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({'passed': True, 'selected_candidate_count': 16,
                  'manifest_sha256': result['manifest_sha256']}))
