"""Bind validated synthetic CPU audit contracts to the partial selected draft."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DRAFT = ROOT / 'draft-selected-execution-manifest.json'
PHYSICAL = ROOT / 'native/physical-fixtures/selected'
DELIVERY = ROOT / 'native/delivery-cpu/checkpoint.json'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    draft = json.loads(DRAFT.read_text())
    delivery = json.loads(DELIVERY.read_text())
    by_case = {row['case_id']: row for row in delivery['cases']}
    assert len(draft['cases']) == len(by_case) == 13
    for entry in draft['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        proof = PHYSICAL / suffix / 'proof.json'
        assert json.loads(proof.read_text())['construction_sha256'] == entry['construction_sha256']
        entry['physical_preparation'] = {'receipt': str(proof.relative_to(ROOT)),
                                         'sha256': sha(proof)}
        row = by_case[case]
        assert row['script_sha256'] == sha(ROOT / row['script'])
        assert row['positive_log_sha256'] == sha(ROOT / row['positive_log'])
        assert row['negative_log_sha256'] == sha(ROOT / row['negative_log'])
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': row['script'], 'script_sha256': row['script_sha256'],
            'command': row['positive_command'],
            'test_exit_code': row['positive_exit_code'],
            'test_log': row['positive_log'],
            'test_log_sha256': row['positive_log_sha256'],
            'negative_command': row['negative_command'],
            'negative_exit_code': row['negative_exit_code'],
            'negative_expected_error': 'Synthetic fixture cannot establish original Native delivery',
            'negative_log': row['negative_log'],
            'negative_log_sha256': row['negative_log_sha256'],
            'scope': 'CPU audit boundary only; original Native delivery unverified'}
        entry['remaining_cpu_bindings'] = [item for item in entry['remaining_cpu_bindings']
                                           if item not in ('per_case_physical_preparation',
                                                           'delivery_acceptance_positive_and_negative')]
    DRAFT.write_text(json.dumps(draft, indent=2, allow_nan=False) + '\n')
    print('PASS bound 13 exact synthetic physical and delivery audit CPU contracts')


if __name__ == '__main__':
    main()
