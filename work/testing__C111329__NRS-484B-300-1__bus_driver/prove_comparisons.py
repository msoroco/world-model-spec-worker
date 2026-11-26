"""Mock-only original comparison audit positive and source-negative proof."""
import json
from pathlib import Path

from delivery_audit import audit_comparisons
from package_spec import CASES, HERE, ROOT, case_id


def main():
    reports = {case_id(name): json.loads((ROOT / '.runtime-work/c111329/delivery' /
                name / 'report.json').read_text()) for name, *_ in CASES}
    comparisons = audit_comparisons(reports, allow_mock=True)
    if len(comparisons) != 3 or any(item['legal_status'] != 'unresolved' or
                                    item['physical_acceptance'] is not False
                                    for item in comparisons):
        raise ValueError('three source-gated comparison probes incomplete')
    try:
        audit_comparisons(reports)
    except ValueError as error:
        if 'nonoriginal' not in str(error):
            raise
    else:
        raise ValueError('mock-only comparison accepted for production')
    corrupt = {key: dict(value) for key, value in reports.items()}
    first = case_id(CASES[0][0])
    corrupt[first]['source_kind'] = 'synthetic_diagnostic_fixture'
    try:
        audit_comparisons(corrupt, allow_mock=True)
    except ValueError as error:
        if 'nonoriginal' not in str(error):
            raise
    else:
        raise ValueError('synthetic comparison source accepted')
    receipt = {'format': 'c111329-mock-only-comparison-wiring-v1',
               'diagnostic_fixture': True, 'original_acceptance': False,
               'physical_acceptance': False, 'legal_verdict': None,
               'missing_original_source_rejected': True,
               'case_count': 4, 'comparison_count': 3,
               'comparison_ids': [item['comparison_id'] for item in comparisons]}
    (HERE / 'comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('three mock-only comparison wiring probes passed')


if __name__ == '__main__':
    main()
