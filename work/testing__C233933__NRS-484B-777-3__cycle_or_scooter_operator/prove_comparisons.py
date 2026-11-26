"""Exercise three exact comparison protocols and changed-source rejection."""
import hashlib
import json
from pathlib import Path
from comparison_audit import FIXED_FIELDS, ComparisonError, audit
from package_spec import AID

HERE = Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def run():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases = {row['case_id']: row for row in plan['cases']}
    if plan['assignment_id'] != AID or len(plan['comparisons']) != 3:
        raise ValueError('three exact comparisons required')
    reports = []
    for comparison in plan['comparisons']:
        records = []
        for case_id in comparison['case_ids']:
            case = cases[case_id]
            observables = {
                'rider_count': case['requested_rider_count'],
                'exclusive_use_designation': case['requested_exclusive_use'],
                'occupied_surface_kind': case['requested_roadway_occupancy']}
            record = {'format': 'rider-formation-delivery-measurement', 'case_id': case_id,
                      'native_result_sha256': hashlib.sha256(case_id.encode()).hexdigest(),
                      'frame_count': 900, 'full_video_decode': True, 'actual_pixels': True,
                      'physical_completion': True, 'observables': observables,
                      'diagnostic_fixture': True, 'legal_abreast_judgment': None,
                      'legal_exclusive_use_judgment': None, 'legal_verdict': None}
            record.update({field: 'synthetic-fixed-' + field for field in FIXED_FIELDS})
            record['duration_frames'] = 900
            records.append(record)
        positive = audit(records, deliberate_differences=comparison['deliberate_differences'])
        negative = json.loads(json.dumps(records))
        negative[1]['bicycle_classification_sha256'] = 'changed-classification'
        try:
            audit(negative, deliberate_differences=comparison['deliberate_differences'])
        except ComparisonError as error:
            if 'fixed condition changed: bicycle_classification_sha256' not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError('changed bicycle classification accepted')
        log = HERE / ('proof-comparison-' + comparison['comparison_id'] + '.log')
        log.write_text('positive: ' + positive['status'] + '\nnegative: ' + negative_error +
                       '\nsynthetic CPU protocol; Native acceptance false\n')
        reports.append({'comparison_id': comparison['comparison_id'], 'case_ids': comparison['case_ids'],
                        'script': 'comparison_audit.py', 'script_sha256': sha(HERE / 'comparison_audit.py'),
                        'diagnostic_fixture': True, 'source_verified': False, 'positive_exit_code': 0,
                        'negative_rejected': True, 'log': log.name, 'log_sha256': sha(log), 'legal_verdict': None})
    (HERE / 'comparison-proposal.json').write_text(json.dumps({
        'format': 'rider-formation-exact-comparison-proposal', 'assignment_id': AID,
        'comparisons': reports, 'legal_verdict': None}, indent=2) + '\n')
    return len(reports)

if __name__ == '__main__':
    print('rider-formation comparison CPU proofs:', run())
