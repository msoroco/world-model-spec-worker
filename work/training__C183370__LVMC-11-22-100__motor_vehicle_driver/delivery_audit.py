"""Independently audit source-bound C183370 delivery preparation.

Diagnostic mode checks saved software joins and always rejects acceptance.
Original mode additionally requires independently reviewed source citations and
a separate physical review. This script never decides the statutory verdict
or canonical set membership.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
import review_annotations
import review_variant_annotations

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CORE_SOURCES = ('capture-receipt.json', 'acquisition-provenance.json',
                'native-actors.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                'road.xodr', 'live-readback.json',
                *(name + '.mkv' for name in CAMERAS))
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_review(attempt, short):
    analysis_path = attempt / 'source-analysis.json'
    annotations_path = attempt / 'source-review-annotations.json'
    require(analysis_path.is_file() and annotations_path.is_file(),
            'Independent original source review required')
    analysis, annotations = read(analysis_path), read(annotations_path)
    if short in ('reference', 'contrast'):
        require(analysis.get('case') == short,
                'Original review case differs from selected case')
    else:
        controls = {'barrier_': 'barrier',
                    'warning_sign_': 'warning_sign',
                    'highway_closed_sign_': 'highway_closed_sign',
                    'employee_exception_': 'employee_exception'}
        matches = [(prefix, kind) for prefix, kind in controls.items()
                   if short.startswith(prefix)]
        require(len(matches) == 1, 'Unknown selected statutory variant')
        prefix, kind = matches[0]
        require(analysis.get('control_kind') == kind and
                analysis.get('case') == short[len(prefix):],
                'Original review variant differs from selected case')
    for name, expected in analysis.get('source_hashes', {}).items():
        require(sha(attempt / name) == expected,
                'Reviewed original source changed: ' + name)
    for camera in analysis['camera_sources']:
        name = camera['name'] + '.mkv'
        require(sha(attempt / name) == camera['source_sha256'],
                'Reviewed original camera changed: ' + name)
    if short in ('reference', 'contrast'):
        review = review_annotations.evaluate(
            analysis, annotations, analysis_sha256=sha(analysis_path))
    else:
        activity = annotations.get('annotations', {}).get('operator_activity')
        if short.startswith(('barrier_', 'warning_sign_',
                             'highway_closed_sign_')):
            require(isinstance(activity, dict) and
                    activity.get('status') == 'not_actually_engaged',
                    'Original nonemployee activity review required')
        if activity:
            evidence = activity.get('independent_evidence', {})
            reference = Path(evidence.get('reference', ''))
            require(reference.parts and not reference.is_absolute()
                    and '..' not in reference.parts
                    and isinstance(evidence.get('observation'), str)
                    and len(evidence['observation'].strip()) >= 20
                    and sha(attempt / reference) == evidence.get('sha256'),
                    'Original operator activity source changed')
        review = review_variant_annotations.evaluate(
            analysis, annotations, analysis_sha256=sha(analysis_path))
        flagger = annotations.get('annotations', {}).get('fixed_flagger_conduct')
        require(isinstance(flagger, dict) and flagger.get('status') in (
                    'warning_observed', 'not_observed_in_reviewed_interval',
                    'indeterminate'),
                'Original fixed flagger conduct review required')
        cameras = {row['name']: row['source_sha256']
                   for row in analysis['camera_sources']}
        require(flagger.get('camera') in cameras and
                flagger.get('camera_sha256') == cameras[flagger['camera']],
                'Original fixed flagger camera source changed')
        first = analysis['observations']['source_first_frame']
        last = analysis['observations']['source_last_frame']
        interval = flagger.get('frame_interval')
        context = review['control_and_repair_overlap_frames']
        require(isinstance(interval, list) and len(interval) == 2 and
                all(type(frame) is int for frame in interval) and
                first <= interval[0] <= interval[1] <= last and
                max(interval[0], context[0]) <= min(interval[1], context[1]) and
                isinstance(flagger.get('observation'), str) and
                len(flagger['observation'].strip()) >= 20,
                'Original fixed flagger conduct needs cited context')
        if flagger['status'] == 'warning_observed':
            require(flagger.get('warning_content') ==
                    'against_riding_or_driving_over_identified_pavement',
                    'Fixed flagger warning content not reviewed')
    require(review['requested_contact_context_observed'] is True,
            'Requested contact context not observed in original sources')
    expected_activity = ('actually_engaged' if short ==
                         'employee_exception_employee_crossing'
                         else 'not_actually_engaged')
    observed_activity = review['paving_employee_exception_status']
    if short.startswith(('barrier_', 'warning_sign_',
                         'highway_closed_sign_')):
        observed_activity = annotations['annotations']['operator_activity']['status']
    require(observed_activity == expected_activity,
            'Paving employee exception unresolved for selected comparison')
    if short in ('reference', 'contrast'):
        evidence = annotations['annotations']['paving_employee_exception'][
            'independent_evidence']
        reference = Path(evidence['reference'])
        require(reference.parts and not reference.is_absolute()
                and '..' not in reference.parts
                and sha(attempt / reference) == evidence['sha256'],
                'Original employee exception source changed')
    return {'analysis_sha256': sha(analysis_path),
            'annotations_sha256': sha(annotations_path),
            'reviewer_id': review['reviewer_id'],
            'reviewed_contact_frames': len(
                review.get('contact_during_reviewed_context_frames', [])),
            'employee_exception_status': expected_activity,
            'fixed_flagger_conduct_status': (
                flagger['status'] if short not in ('reference', 'contrast')
                else 'governing_warning_person')}


def validate_physical_review(physical, *, case, candidate, manifest_sha256,
                             processing_sha256, reviewed, source_hashes):
    require(physical.get('format') == 'c183370-independent-physical-review-v1'
            and physical.get('passed') is True
            and physical.get('case_id') == case
            and physical.get('candidate_id') == candidate
            and physical.get('manifest_sha256') == manifest_sha256
            and physical.get('processing_sha256') == processing_sha256
            and physical.get('source_analysis_sha256') ==
            reviewed['analysis_sha256']
            and physical.get('source_annotations_sha256') ==
            reviewed['annotations_sha256']
            and physical.get('original_source_sha256') == source_hashes
            and physical.get('checks') == {name: True for name in CHECKS}
            and isinstance(physical.get('reviewer_id'), str)
            and physical['reviewer_id'].strip()
            and physical['reviewer_id'] != reviewed['reviewer_id']
            and physical.get('legal_verdict_claimed') is False,
            'Independent physical review bindings or checks incomplete')


def audit(manifest_path, case, candidate, attempt, processing_path, diagnostic):
    manifest_path, attempt, processing_path = map(
        Path, (manifest_path, attempt, processing_path))
    manifest = read(manifest_path)
    require(manifest['assignment_id'] == HERE.name,
            'Delivery audit assignment differs')
    entry = next((row for row in manifest['cases']
                  if row['case_id'] == case), None)
    require(entry is not None and case.startswith(HERE.name + '__'),
            'Unselected delivery case')
    short = case[len(HERE.name) + 2:]
    selected = entry if candidate == 'primary' else next(
        (row for row in entry['candidates'] if row['id'] == candidate), None)
    require(selected is not None and
            sha(HERE / selected['construction']) == selected['construction_sha256'],
            'Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    require(selection['case_id'] == case and
            selection['candidate_id'] == candidate and
            selection['manifest_sha256'] == sha(manifest_path) and
            selection['construction_sha256'] == selected['construction_sha256'],
            'Candidate selection differs')
    processing = read(processing_path)
    require(processing['passed'] is True and
            processing['recorded_only'] is True and
            processing['originals_preserved'] is True and
            processing['missing_evidence'] is False and
            processing['case_id'] == case and
            processing['candidate_id'] == candidate and
            processing['analysis_revision']['construction_sha256'] ==
            selected['construction_sha256'] and
            processing['timestamp_joins']['passed'] is True and
            processing['timestamp_joins']['frames'] >= 600 and
            processing['final_video_checks']['passed'] is True and
            processing['final_video_checks']['frames'] >= 600 and
            processing['physical_acceptance_claimed'] is False and
            processing['legal_acceptance_claimed'] is False,
            'Saved source proof incomplete')
    hashes = {}
    for name in CORE_SOURCES:
        path = attempt / name
        require(path.is_file(), 'Missing original source: ' + name)
        hashes[name] = sha(path)
        require(processing['original_source_hashes'].get(name) == hashes[name],
                'Saved original source changed: ' + name)
    receipt = read(attempt / 'capture-receipt.json')
    provenance = read(attempt / 'acquisition-provenance.json')
    require(receipt['source_frames'] >= 600 and receipt['capture_rate_hz'] == 20
            and set(receipt['four_cameras']) ==
            {name + '.mkv' for name in CAMERAS},
            'Original capture duration or camera contract differs')
    result_path = Path(processing['result'])
    require(result_path.is_file() and
            sha(result_path) == processing['result_sha256'],
            'Saved result changed')
    result = read(result_path)
    require(result['case_id'] == case and result['accepted'] is False
            and result['legal_verdict_claimed'] is False,
            'Saved result asserted acceptance or another case')
    if diagnostic:
        require(provenance['diagnostic_fixture'] is True and
                receipt['source_kind'] == 'synthetic_diagnostic_capture',
                'Diagnostic audit needs explicit synthetic provenance')
        return {'format': 'c183370-delivery-audit-v1', 'case_id': case,
                'candidate_id': candidate, 'diagnostic_only': True,
                'accepted': False, 'checks': {
                    name: name in ('all_participants', 'time_join',
                                   'full_video_decode') for name in CHECKS},
                'manifest_sha256': sha(manifest_path),
                'original_source_sha256': hashes,
                'original_native_verified': False,
                'physical_or_legal_acceptance_claimed': False}
    require(manifest_path.resolve() == (HERE / 'execution-manifest.json').resolve() and
            manifest['format'] == 'worker-execution-manifest' and
            receipt['source_kind'] == 'original_carla_capture' and
            provenance['diagnostic_fixture'] is False and
            provenance['provenance_kind'] == 'native',
            'Original Native source required')
    reviewed = source_review(attempt, short)
    physical_path = attempt / 'independent-physical-review.json'
    require(physical_path.is_file(), 'Independent physical review required')
    physical = read(physical_path)
    validate_physical_review(
        physical, case=case, candidate=candidate,
        manifest_sha256=sha(manifest_path),
        processing_sha256=sha(processing_path), reviewed=reviewed,
        source_hashes=hashes)
    return {'format': 'c183370-delivery-audit-v1', 'case_id': case,
            'candidate_id': candidate, 'diagnostic_only': False,
            'accepted': True, 'checks': {name: True for name in CHECKS},
            'manifest_sha256': sha(manifest_path),
            'original_source_sha256': hashes, 'source_review': reviewed,
            'physical_review_sha256': sha(physical_path),
            'original_native_verified': True,
            'physical_acceptance_claimed': True,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('manifest', 'case', 'candidate', 'attempt', 'processing',
                 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.manifest, args.case, args.candidate,
                  args.attempt, args.processing, args.diagnostic)
    output = Path(args.output)
    require(not output.exists(), 'Retain previous delivery audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'case_id': args.case, 'candidate_id': args.candidate,
                      'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}, sort_keys=True))
