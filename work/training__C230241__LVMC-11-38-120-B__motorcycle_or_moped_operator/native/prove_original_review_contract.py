"""Exercise provenance requirements without claiming original pixels were reviewed."""
import copy
import json
from pathlib import Path

from selected_source_analysis import REVIEW_EVIDENCE, validate_original_review_provenance, sha


def reject(context, rows, expected):
    try:
        validate_original_review_provenance(context, rows)
    except ValueError as error:
        if str(error) != expected:
            raise
    else:
        raise AssertionError('Missing original review provenance accepted')


def main():
    context = {
        'source_kind': 'calibrated_original_review',
        'diagnostic_only': False,
        'reviewer': 'synthetic contract test',
        'range_calibration_source': 'synthetic contract test calibration',
        'visibility_review_source': 'synthetic contract test visibility',
        'camera_evidence': ['overview.mkv', 'approach.mkv',
                            'reference_corner.mkv', 'driver_reference.mkv'],
    }
    rows = [dict(video_frame=i, source_kind='calibrated_original_review',
                 **{key: 'synthetic frame source ' + str(i) for key in REVIEW_EVIDENCE})
            for i in range(600)]
    validate_original_review_provenance(context, rows)
    negative = copy.deepcopy(rows)
    del negative[300]['front_range_source']
    reject(context, negative, 'Original review lacks frame source: front_range_source')
    negative = copy.deepcopy(rows)
    negative[300]['video_frame'] = 299
    reject(context, negative, 'Original review frame identity differs at 300')
    negative_context = dict(context)
    del negative_context['range_calibration_source']
    reject(negative_context, rows,
           'Original review missing provenance: range_calibration_source')
    receipt = {'format': 'c230241-original-review-contract-test-v1',
               'passed': True, 'synthetic_contract_test': True,
               'checks': ['complete 600-frame provenance', 'missing range source rejected',
                          'duplicate frame identity rejected', 'missing calibration rejected'],
               'analysis_script_sha256': sha(Path(__file__).with_name('selected_source_analysis.py')),
               'original_pixels_reviewed': False, 'physical_visibility_verified': False,
               'legal_verdict_claimed': False}
    target = Path(__file__).with_name('original-review-contract-proof.json')
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'checks': len(receipt['checks'])}))


if __name__ == '__main__':
    main()
