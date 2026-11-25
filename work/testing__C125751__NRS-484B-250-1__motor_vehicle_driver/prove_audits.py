"""Positive and adversarial CPU checks of independent delivery/comparison audits."""
import copy
import json
from pathlib import Path

import audit_comparisons
import audit_delivery

ROOT = Path(__file__).resolve().parent


def must_reject(call, expected):
    try:
        call()
    except (ValueError, FileNotFoundError) as error:
        if expected not in str(error):
            raise AssertionError('Wrong rejection: ' + str(error)) from error
    else:
        raise AssertionError('Tampered proof was accepted')


def run():
    delivery = audit_delivery.audit(ROOT)
    comparisons = audit_comparisons.audit(ROOT)
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    altered = copy.deepcopy(manifest)
    altered['cases'][0]['compatibility']['sha256'] = '0' * 64
    must_reject(lambda: audit_delivery.audit(ROOT, altered),
                'Changed compatibility receipt')
    entries = {x['case_id'].split('__')[-1]: x for x in manifest['cases']}
    left = audit_comparisons.load_case(entries['source_verified_signal_exclusion'], ROOT)
    right = audit_comparisons.load_case(entries['source_verified_off_subsection_4'], ROOT)
    altered_right = copy.deepcopy(right)
    altered_right['measured']['device_context']['value']['observed_signal_states'] = ['Green'] * 3
    must_reject(lambda: audit_comparisons.audit_pair('active_vs_off_signal_applicability',
                                                     left, altered_right),
                'Signal-state difference')
    return {'delivery_passed': delivery['passed'],
            'comparison_count': len(comparisons['comparisons']),
            'missing_bound_receipt_rejected': True,
            'wrong_signal_state_rejected': True,
            'diagnostic_fixture_only': True}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
