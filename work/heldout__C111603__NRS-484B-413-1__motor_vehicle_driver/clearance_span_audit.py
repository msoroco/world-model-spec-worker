"""Source-bound three-way clearance comparison, without a safety verdict."""
import argparse
import json
from pathlib import Path

from clearance_wide_audit import audit as audit_wide
from clearance_narrow_audit import audit as audit_narrow


def audit(baseline, wide, narrow):
    wide_receipt = audit_wide(wide, baseline)
    narrow_receipt = audit_narrow(narrow, baseline)
    baseline_gap = wide_receipt['baseline_minimum_sampled_gap_m']
    if baseline_gap != narrow_receipt['baseline_minimum_sampled_gap_m']:
        raise ValueError('Clearance comparisons used different baseline sources')
    wide_gap = wide_receipt['wide_minimum_sampled_gap_m']
    narrow_gap = narrow_receipt['narrow_minimum_sampled_gap_m']
    if not narrow_gap < baseline_gap < wide_gap:
        raise ValueError('Original sampled clearance ordering differs')
    if (wide_receipt['physical_safety_verified'] or narrow_receipt['physical_safety_verified'] or
            wide_receipt['legal_acceptance_claimed'] or narrow_receipt['legal_acceptance_claimed']):
        raise ValueError('Clearance comparison overclaimed physical or legal safety')
    return {'format': 'worker-clearance-span-audit',
            'baseline_case_id': wide_receipt['baseline_case_id'],
            'wide_case_id': wide_receipt['case_id'],
            'narrow_case_id': narrow_receipt['case_id'],
            'original_source_pair_audits_passed': True,
            'minimum_sampled_gap_m': {'narrow': narrow_gap, 'baseline': baseline_gap, 'wide': wide_gap},
            'physical_safety_verified': False, 'legal_acceptance_claimed': False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--baseline', required=True)
    p.add_argument('--wide', required=True)
    p.add_argument('--narrow', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    receipt = audit(args.baseline, args.wide, args.narrow)
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt['minimum_sampled_gap_m']))


if __name__ == '__main__':
    main()
