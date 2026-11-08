"""Independently audit all exact 1(b) synthetic Core/video package receipts."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest_path = FOLDER / 'draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    summary = json.loads((FOLDER / 'full-package-summary.json').read_text())
    proposal = json.loads((FOLDER / 'proposals/cases.json').read_text())
    assert summary['manifest_sha256'] == sha(manifest_path)
    assert summary['original_native_or_delivery_acceptance_claimed'] is False
    assert proposal['status'] == 'unselected_cpu_draft'
    assert {x['case_id'] for x in proposal['cases']} == {x['case_id'] for x in manifest['cases']}
    rows = {(row['case_id'], row['candidate_id']): row for row in summary['results']}
    assert len(rows) == 8
    audited = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            row = rows[(entry['case_id'], candidate)]
            selected = entry if candidate == 'primary' else next(
                x for x in entry['candidates'] if x['id'] == candidate)
            construction_path = FOLDER / selected['construction']
            assert row['construction_sha256'] == selected['construction_sha256'] == sha(construction_path)
            construction = json.loads(construction_path.read_text())
            proposal_case = next(x for x in proposal['cases'] if x['case_id'] == entry['case_id'])
            assert proposal_case['recording_description'] == construction['recording_description']
            analysis = next(x['content'] for x in construction['files'] if x['path'] == 'finalize.py')
            folder = FOLDER / 'draft-candidates' / case / candidate
            proof_path = folder / 'full-package-proof.json'
            assert json.loads(proof_path.read_text()) == row
            compatibility_path = folder / 'full-compatibility.json'
            decode_path = folder / 'full-final-decode.json'
            negative_path = folder / 'full-negative.log'
            assert row['compatibility_sha256'] == sha(compatibility_path)
            assert row['final_decode_sha256'] == sha(decode_path)
            assert row['negative_log_sha256'] == sha(negative_path)
            assert row['negative_error'] in negative_path.read_text()
            receipt = json.loads(compatibility_path.read_text())
            assert receipt['format'] == 'worker-package-compatibility-v1'
            assert receipt['passed'] is True and REQUIRED <= set(receipt['checks'])
            assert receipt['checks'] == row['positive_checks']
            assert receipt['case_id'] == entry['case_id'] and receipt['candidate_id'] == candidate
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
            assert receipt['analysis_sha256'] == hashlib.sha256(analysis.encode()).hexdigest()
            assert receipt['scope'] == 'diagnostic software compatibility only'
            decode = json.loads(decode_path.read_text())
            assert decode.get('passed') is True and decode.get('frames') == 480
            log_path = (FOLDER / 'full-package-probe.log' if (case, candidate) == ('reference', 'primary')
                        else folder / 'full-package-command.log')
            log_lines = log_path.read_text().splitlines()
            assert log_lines[0].startswith('scratch ')
            scratch = Path(log_lines[0].removeprefix('scratch '))
            result = json.loads((scratch / 'output/result.json').read_text())
            assert result['case_id'] == entry['case_id']
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert result['target_checks'][0]['physical_cause_confirmed'] is False
            assert sha(scratch / 'output/compatibility-analysis.log') == receipt['log_sha256']
            assert (scratch / 'output/converted/atom_contract.json').is_file()
            assert (scratch / 'output/converted/trace.json').is_file()
            audited.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': selected['construction_sha256'],
                            'compatibility_sha256': row['compatibility_sha256'],
                            'negative_log_sha256': row['negative_log_sha256']})
    audit_result = {'passed': True, 'exact_unselected_synthetic_v1_rows': len(audited),
                    'positive_count': len(audited), 'negative_count': len(audited),
                    'strict_v2_or_original_native_claimed': False, 'rows': audited}
    (FOLDER / 'full-package-audit.json').write_text(json.dumps(audit_result, indent=2) + '\n')
    return audit_result


if __name__ == '__main__':
    result = audit()
    print(json.dumps({'passed': result['passed'],
                      'rows': result['exact_unselected_synthetic_v1_rows']}))
