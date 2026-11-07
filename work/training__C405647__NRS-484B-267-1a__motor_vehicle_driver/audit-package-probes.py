"""Audit retained exact synthetic package receipts without promoting a case."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    negative_proof = json.loads((HERE / 'draft-package-negative-proof.json').read_text())
    assert negative_proof['passed'] is True and negative_proof['negative_count'] == 8
    negative_rows = {(row['case_id'], row['candidate_id']): row
                     for row in negative_proof['rows']}
    assert len(negative_rows) == 8
    rows = []
    for case, entry in zip(CASES, manifest['cases']):
        assert entry['case_id'].endswith('__' + case)
        for candidate in CANDIDATES:
            label = 'draft-package-probe.log' if (case, candidate) == ('witness_1', 'primary') else (
                f'draft-package-{case}-{candidate}.log')
            log = HERE / label
            lines = log.read_text().splitlines()
            assert len(lines) == 2 and lines[0].startswith('scratch ')
            record = json.loads(lines[1])
            scratch = Path(lines[0].removeprefix('scratch '))
            output = scratch / 'output'
            receipt = json.loads((output / 'compatibility.json').read_text())
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            assert record['case_id'] == entry['case_id']
            assert record['candidate_id'] == candidate
            assert record['positive'] == {key: value for key, value in receipt.items()
                                          if key != 'fixture_manifest'}
            assert receipt['format'] == 'worker-package-compatibility-v1'
            assert receipt['passed'] is True
            assert receipt['construction_sha256'] == selected['construction_sha256']
            assert receipt['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256']
            assert {'actual_analysis', 'native_validation', 'mandatory_observations',
                    'lean_decoder', 'render', 'final_decode',
                    'acquisition_unchanged'} <= set(receipt['checks'])
            assert sha(output / 'compatibility-analysis.log') == receipt['log_sha256']
            assert (output / 'converted/trace.json').is_file()
            assert (output / 'converted/atom_contract.json').is_file()
            assert (output / 'final-decode.json').is_file()
            result = json.loads((output / 'result.json').read_text())
            assert result['accepted'] is False
            assert result['setup_confirmed'] is False
            assert result['behavior_attempted'] is False
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            negative_log = HERE / 'draft-package-negatives' / f'{case}-{candidate}.log'
            assert record['negative'] == {'removed': 'source-scope.json', 'exit_code': 1,
                                          'log_sha256': sha(negative_log)}
            assert 'Missing required source: source-scope.json' in negative_log.read_text()
            negative_row = negative_rows[(entry['case_id'], candidate)]
            assert negative_row['negative_log'] == str(negative_log.relative_to(HERE))
            assert negative_row['negative_log_sha256'] == sha(negative_log)
            assert negative_row['expected_error'] in negative_log.read_text()
            assert not (scratch / 'negative/source-scope.json').exists()
            rows.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                         'construction_sha256': selected['construction_sha256'],
                         'log_sha256': sha(log), 'compatibility_sha256': sha(output / 'compatibility.json'),
                         'final_decode_sha256': sha(output / 'final-decode.json'),
                         'negative_log_sha256': sha(negative_log)})
    return {'passed': True, 'exact_unselected_synthetic_v1_rows': len(rows),
            'strict_v2_or_physical_claimed': False, 'rows': rows}


if __name__ == '__main__':
    result = audit()
    (HERE / 'draft-package-probe-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': result['passed'],
                      'exact_unselected_synthetic_v1_rows': len(result['rows']),
                      'strict_v2_or_physical_claimed': False}))
