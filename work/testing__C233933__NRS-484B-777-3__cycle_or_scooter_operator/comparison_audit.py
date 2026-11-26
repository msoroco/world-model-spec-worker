"""Independent comparison protocol for rider count and exclusive-use designation."""
import argparse
import json
from pathlib import Path

class ComparisonError(ValueError):
    pass

FIXED_FIELDS = ('map_sha256', 'reviewed_site_sha256', 'highway_status_sha256',
                'bicycle_classification_sha256', 'bicycle_blueprint',
                'ego_rider_id', 'control_rider_id', 'camera_plan_sha256', 'duration_frames')

def audit(records, *, deliberate_differences):
    if len(records) != 2 or not deliberate_differences:
        raise ComparisonError('two separate records and deliberate differences required')
    for row in records:
        if row.get('format') != 'rider-formation-delivery-measurement' or not row.get('case_id') or not row.get('native_result_sha256'):
            raise ComparisonError('missing sealed Native measurement')
        if row.get('frame_count') != 900 or row.get('full_video_decode') is not True or not row.get('actual_pixels') or not row.get('physical_completion'):
            raise ComparisonError('incomplete physical or pixel evidence')
        if (row.get('legal_abreast_judgment') is not None or
                row.get('legal_exclusive_use_judgment') is not None or
                row.get('legal_verdict') is not None):
            raise ComparisonError('legal rider judgment is unresolved')
        for field in FIXED_FIELDS:
            if row.get(field) in (None, ''):
                raise ComparisonError('missing fixed condition: ' + field)
    if records[0]['case_id'] == records[1]['case_id'] or records[0]['native_result_sha256'] == records[1]['native_result_sha256']:
        raise ComparisonError('separate Native captures required')
    for field in FIXED_FIELDS:
        if records[0][field] != records[1][field]:
            raise ComparisonError('fixed condition changed: ' + field)
    for field in deliberate_differences:
        values = [row.get('observables', {}).get(field) for row in records]
        if None in values or json.dumps(values[0], sort_keys=True) == json.dumps(values[1], sort_keys=True):
            raise ComparisonError('deliberate difference absent: ' + field)
    return {'format': 'rider-formation-comparison-audit', 'case_ids': [row['case_id'] for row in records],
            'fixed_conditions_checked': list(FIXED_FIELDS), 'deliberate_differences': deliberate_differences,
            'status': 'measurement_comparable_legal_abreast_unresolved'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--records', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    plan = json.loads((here / 'case-plan.json').read_text())
    found = [row for row in plan['comparisons'] if row['comparison_id'] == args.comparison]
    if len(found) != 1:
        raise ComparisonError('unknown comparison')
    records = json.loads(args.records.read_text())
    ids = found[0]['case_ids']
    if set(records) != set(ids):
        raise ComparisonError('comparison identities changed')
    result = audit([records[case_id] for case_id in ids], deliberate_differences=found[0]['deliberate_differences'])
    result['comparison_id'] = args.comparison
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
