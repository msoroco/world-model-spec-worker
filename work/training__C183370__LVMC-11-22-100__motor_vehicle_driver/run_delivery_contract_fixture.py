"""Check original-source audit bindings without asserting a Native capture."""
import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import CHECKS, validate_physical_review

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == args.case), None)
    if entry is None:
        raise ValueError('Unknown selected case')
    # These are deliberately synthetic digest-shaped values. This proves the
    # contract's source binding and missing-check rejection, not source truth.
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    reviewed = {'analysis_sha256': digest('analysis:' + args.case),
                'annotations_sha256': digest('annotations:' + args.case),
                'reviewer_id': 'synthetic-source-reviewer'}
    sources = {'capture-receipt.json': digest('capture:' + args.case)}
    checks = {name: True for name in CHECKS}
    if args.negative:
        checks['actual_pixels'] = False
    physical = {
        'format': 'c183370-independent-physical-review-v1',
        'passed': True, 'case_id': args.case, 'candidate_id': 'primary',
        'manifest_sha256': hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'processing_sha256': digest('processing:' + args.case),
        'source_analysis_sha256': reviewed['analysis_sha256'],
        'source_annotations_sha256': reviewed['annotations_sha256'],
        'original_source_sha256': sources, 'checks': checks,
        'reviewer_id': 'synthetic-physical-reviewer',
        'legal_verdict_claimed': False,
    }
    validate_physical_review(
        physical, case=args.case, candidate='primary',
        manifest_sha256=physical['manifest_sha256'],
        processing_sha256=physical['processing_sha256'],
        reviewed=reviewed, source_hashes=sources)
    print(json.dumps({'case_id': args.case, 'contract_shape_passed': True,
                      'synthetic_fixture': True,
                      'original_native_verified': False,
                      'physical_or_legal_acceptance_claimed': False},
                     sort_keys=True))


if __name__ == '__main__':
    main()
