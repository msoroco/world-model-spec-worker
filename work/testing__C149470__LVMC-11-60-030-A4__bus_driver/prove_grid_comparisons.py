"""Mock-only positive and source-negative wiring proof for seven original comparisons."""
import hashlib
import json
from pathlib import Path

from bus_curb import CASES
from delivery_audit import audit_comparisons
from reviewed_source import FIELDS

HERE = Path(__file__).resolve().parent


def source_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def reports():
    output = {}
    for case in CASES:
        hashes = {field: source_hash('mock-only fixed ' + field) for field in FIELDS}
        if case.name.startswith('parallel_source_review-'):
            hashes['bus_route'] = source_hash('mock-only bus route ' + str(case.heading_request_deg))
        if case.name.startswith('traffic_impediment_source_review-'):
            hashes['traffic_route'] = source_hash('mock-only traffic route ' + str(case.traffic_lateral_request_m))
        case_id = HERE.name + '__' + case.name
        output[case_id] = {'format': 'c149470-independent-original-attempt-audit-v1',
                           'case_id': case_id, 'source_kind': 'original_native_capture',
                           'legal_status': 'unresolved', 'physical_acceptance': False,
                           'source_hashes': hashes,
                           'measurement': {'source_hashes': hashes,
                               'right_front_wheel_curb_upper_bound_m': case.target_distance_m + .001,
                               'maximum_bus_curb_angle_deg': case.heading_request_deg,
                               'minimum_other_traffic_speed_mps': 3.0}}
    return output


def main():
    mock = reports()
    diagnostic = audit_comparisons(mock)
    if len(diagnostic) != 7 or any(item['legal_status'] != 'unresolved' or
                                    item['physical_acceptance'] is not False
                                    for item in diagnostic):
        raise ValueError('seven comparison wiring probes incomplete')
    first = next(iter(mock))
    mock[first]['source_kind'] = 'synthetic_diagnostic_fixture'
    try:
        audit_comparisons(mock)
    except ValueError as error:
        if 'nonoriginal' not in str(error):
            raise
    else:
        raise ValueError('synthetic source accepted as original')
    receipt = {'format': 'c149470-mock-only-comparison-wiring-v1',
               'case_count': len(CASES), 'comparison_count': len(diagnostic),
               'diagnostic_fixture': True, 'original_acceptance': False,
               'physical_acceptance': False, 'legal_verdict': None,
               'missing_original_source_rejected': True,
               'comparison_ids': [item['comparison_id'] for item in diagnostic]}
    (HERE / 'grid-comparison-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print('seven mock-only comparison wiring probes passed; synthetic original claim rejected')


if __name__ == '__main__':
    main()
