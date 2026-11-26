"""Independent source-bound taxi delivery audit, without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_original import audit as audit_original
from finalize_original import inspect


VIEWS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def check_pixels(attempt, name, video):
    review = read(attempt / name)
    observations = review.get('source_pixels')
    if not isinstance(observations, list) or not observations:
        raise ValueError('Original actual-pixel review missing: ' + name)
    for item in observations:
        view = item.get('camera')
        frame = item.get('video_frame')
        if (view not in VIEWS or type(frame) is not int or not 0 <= frame < 600 or
                item.get('video_sha256') != video[view]['sha256'] or
                item.get('observed_visible') is not True or
                not item.get('observation')):
            raise ValueError('Original actual-pixel review is not video-bound: ' + name)
    return {'review': name, 'sha256': sha(attempt / name),
            'frames': [item['video_frame'] for item in observations]}


def audit(attempt, case_id, diagnostic_test=False):
    attempt = Path(attempt).resolve()
    config = read(attempt / 'config.json')
    if config.get('case_id') != case_id or config.get('selected_case_id') != case_id:
        raise ValueError('Taxi delivery audit selects another exact case')
    original = audit_original(attempt)
    measured = inspect(attempt, attempt / 'source-manifest.json', 'original_native')
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    reported = analysis.get('measurements', {}).get('taxi_yellow_zone_measurement', {}).get('value')
    if (result.get('case_id') != case_id or result.get('measured_values') != measured or
            reported != measured or measured.get('source_manifest_sha256') !=
            original['source_manifest_sha256']):
        raise ValueError('Taxi delivery analysis changed source-bound measurement')
    pixels = [check_pixels(attempt, name, original['videos']) for name in
              ('taxicab-review.json', 'sign-review.json',
               'passenger-purpose-review.json')]
    if measured['stopped_frames'] != 600 or measured['yellow_zone_body_frames'] != 600:
        raise ValueError('Physical taxi standing within yellow zone incomplete')
    purpose = measured['observed_purpose']
    delta = measured['observed_occupant_count_change']
    doors = measured['observed_door_open_frames']
    if ((purpose == 'loading_passengers' and not (delta > 0 and doors > 0)) or
            (purpose == 'unloading_passengers' and not (delta < 0 and doors > 0)) or
            (purpose == 'waiting_for_passengers' and delta != 0)):
        raise ValueError('Original passenger exchange differs from reviewed purpose')
    return {
        'format': 'c150173-independent-delivery-audit-v1',
        'case_id': case_id, 'source_manifest_sha256': original['source_manifest_sha256'],
        'capture_seal_sha256': original['capture_seal_sha256'],
        'analysis_report_sha256': sha(attempt / 'analysis-report.json'),
        'result_sha256': sha(attempt / 'result.json'),
        'pixel_reviews': pixels,
        'checks': {'native_source': True, 'all_participants': True,
                   'time_join': True, 'full_video_decode': True,
                   'actual_pixels': True, 'physical_completion': True},
        'eligible_for_local_acceptance': not diagnostic_test,
        'diagnostic_test': diagnostic_test,
        'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.attempt, args.case)
    if args.output:
        destination = Path(args.output)
        if destination.exists():
            raise ValueError('Fresh independent delivery audit output required')
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'case_id': args.case,
                      'eligible_for_local_acceptance': report['eligible_for_local_acceptance']}))
