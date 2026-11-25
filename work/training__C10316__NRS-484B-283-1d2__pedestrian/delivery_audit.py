"""Source-bound C10316 delivery audit with a synthetic CPU diagnostic mode.

The normal path requires independently reviewed original Native pixels and
governance. Diagnostic mode only proves that the checker can read current
software receipts; it never accepts a physical or legal result.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def audit(case, candidate, attempt, processing, diagnostic):
    manifest = read(HERE / 'execution-manifest.json')
    matches = [e for e in manifest['cases'] if e['case_id'] == case]
    if len(matches) != 1:
        raise ValueError('Exact selected case required')
    entry = matches[0]
    selected = entry if candidate == 'primary' else next(
        (x for x in entry['candidates'] if x['id'] == candidate), None)
    if selected is None:
        raise ValueError('Exact selected candidate required')
    attempt = Path(attempt)
    receipt = read(attempt / 'compatibility.json') if diagnostic else None
    saved = read(processing)
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    if diagnostic and any((receipt.get('passed') is not True,
                           receipt.get('case_id') != case,
                           receipt.get('candidate_id') != candidate,
                           receipt.get('construction_sha256') != selected['construction_sha256'],
                           receipt.get('negative_removed') != 'countdown_samples.jsonl',
                           receipt.get('negative_log_sha256') != sha(attempt / 'negative-analysis.log'))):
        raise ValueError('Current diagnostic compatibility receipt differs')
    if any((saved.get('passed') is not True,
            saved.get('recorded_only') is not True,
            saved.get('case_id') != case,
            saved.get('candidate_id') != candidate,
            saved.get('timestamp_joins', {}).get('frames') != 600,
            saved.get('final_video_checks', {}).get('frames') != 600,
            result.get('accepted') is not False,
            result.get('legal_verdict_claimed') is not False)):
        raise ValueError('Current source-bound compatibility or saved receipt differs')
    measured = analysis['measurements']['flashing_countdown_clearance']['value']
    if measured['original_frames'] != 600 or measured['clearance_relative_to_displayed_zero'] != (
            'before_zero' if case.endswith('probe_01') else 'at_or_after_zero'):
        raise ValueError('Countdown clearance source measurement differs')
    expected_source = 'synthetic_scene_request' if diagnostic else 'native_observation'
    if measured['source_kind'] != expected_source:
        raise ValueError('Original Native source required' if not diagnostic else
                         'Diagnostic source provenance differs')
    if not diagnostic:
        context = read(attempt / 'countdown-context.json')
        review = read(attempt / 'countdown-original-review.json')
        if any((review.get('source_kind') != 'independent_original_pixel_review',
                review.get('governs_crosswalk') is not True,
                review.get('faces_pedestrian') is not True,
                review.get('flashing_indication_legible') is not True,
                review.get('countdown_digits_legible') is not True,
                len(review.get('frame_observations', [])) != 600)):
            raise ValueError('Independent original countdown review incomplete')
        sys.path.insert(0, str(HERE / 'native'))
        from review_countdown import validate as validate_original_countdown_review
        samples = [json.loads(line) for line in
                   (attempt / 'countdown_samples.jsonl').read_text().splitlines()]
        validate_original_countdown_review(attempt, context, samples)
        exceptions = read(attempt / 'statutory-exception-review.json')
        sections = exceptions.get('sections', {})
        if (result.get('maneuver_completed') is not True or
                set(sections) != {'NRS-484B-287', 'NRS-484B-290', 'NRS-484B-350'} or
                any(item.get('review_status') != 'reviewed' or
                    not item.get('original_source_refs') for item in sections.values())):
            raise ValueError('Physical crossing or cited exception context unverified')
    return {'format': 'c10316-countdown-source-bound-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'compatibility_sha256': sha(attempt / 'compatibility.json') if diagnostic else None,
            'processing_sha256': sha(processing),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'source_kind': measured['source_kind'],
            'diagnostic_only': diagnostic,
            'physical_or_legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = audit(args.case, args.candidate, args.attempt, args.processing,
                   args.diagnostic)
    if args.output.exists():
        raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'diagnostic_only': args.diagnostic}))


if __name__ == '__main__':
    main()
