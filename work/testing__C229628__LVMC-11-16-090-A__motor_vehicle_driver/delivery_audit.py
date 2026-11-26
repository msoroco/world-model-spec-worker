"""Independent original pixel, participant and physical review for aid cases."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from contest_aid import CASES
from package_spec import AID, CAMERA_NAMES


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def decoded_frame_sha(video, frame):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video),
                             '-vf', 'select=eq(n\\,' + str(frame) + ')',
                             '-frames:v', '1', '-pix_fmt', 'rgb24',
                             '-f', 'rawvideo', '-'],
                            check=True, capture_output=True)
    need(result.stdout, 'reviewed original frame has no decoded pixels')
    return hashlib.sha256(result.stdout).hexdigest()


def assess(case_id, capture, review, physical, *, diagnostic=False, attempt=None):
    case = next((item for item in CASES if case_id == AID + '__' + item.name), None)
    need(case is not None, 'exact aid case required')
    need(capture.get('case_id') == case_id and capture.get('frame_count') == 900 and
         capture.get('full_decode') is True,
         'full original capture audit missing')
    bindings = capture.get('source_bindings', {})
    need(set(name + '.mkv' for name in CAMERA_NAMES) <= set(bindings),
         'four original camera sources missing')
    need(review.get('case_id') == case_id and
         review.get('capture_receipt_sha256') == capture.get('receipt_sha256'),
         'independent pixel review has wrong source')
    need(review.get('legal_contest_interpretation') is None and
         review.get('legal_aid_abet_interpretation') is None,
         'delivery audit cannot assert legal judgment')
    views = review.get('views')
    need(isinstance(views, dict) and set(views) == set(CAMERA_NAMES),
         'independent four-view review missing')
    cue_samples = []
    for name in CAMERA_NAMES:
        item = views[name]
        need(item.get('video_sha256') == bindings[name + '.mkv'] and
             isinstance(item.get('reviewer'), str) and item['reviewer'].strip(),
             'independent view review missing: ' + name)
        samples = item.get('samples')
        need(isinstance(samples, list) and samples,
             'independent pixel samples missing: ' + name)
        for sample in samples:
            frame = sample.get('frame')
            need(type(frame) is int and 0 <= frame < 900 and
                 sample.get('ego_visible') is True and
                 sample.get('other_visible') is True and
                 isinstance(sample.get('decoded_rgb_sha256'), str) and
                 len(sample['decoded_rgb_sha256']) == 64,
                 'independent participant pixel review incomplete: ' + name)
            if sample.get('cue_visible') is True:
                cue_samples.append((name, frame))
            if not diagnostic:
                need(decoded_frame_sha(Path(attempt) / (name + '.mkv'), frame) ==
                     sample['decoded_rgb_sha256'],
                     'independent pixel source changed: ' + name)
    if case.cue:
        need(any(name in ('approach', 'reference_corner') for name, _ in cue_samples),
             'physical cue not visible in independent pixel review')
    else:
        need(not cue_samples, 'cue appeared in no-cue control')
    maneuver = physical.get('physical_checks', {}).get('maneuver', {})
    need(physical.get('case_id') == case_id and
         physical.get('maneuver_completed') is True and
         maneuver.get('status') == 'met' and maneuver.get('sources') and
         physical.get('realized_observables'),
         'source-measured physical completion missing')
    if not diagnostic:
        need(physical.get('provenance_kind') == 'native' and
             physical.get('diagnostic_fixture') is False,
             'Native physical provenance required')
    return {'format': 'contest-independent-delivery-audit', 'case_id': case_id,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'capture_receipt_sha256': capture['receipt_sha256'],
            'pixel_review_sha256': None, 'source_verified': not diagnostic,
            'diagnostic_fixture': diagnostic, 'canonical_acceptance': False,
            'legal_verdict': None}


def audit(case_id, attempt, review_path, physical_path, *, diagnostic_fixture=False):
    attempt = Path(attempt).resolve()
    review_path = Path(review_path).resolve()
    physical_path = Path(physical_path).resolve()
    need(review_path.is_file(), 'independent pixel review missing')
    need(physical_path.is_file(), 'physical result missing')
    if diagnostic_fixture:
        capture_path = attempt / 'diagnostic-capture-audit.json'
        need(capture_path.is_file(), 'diagnostic capture protocol missing')
        capture = json.loads(capture_path.read_text())
    else:
        from contest_capture_audit import audit as capture_audit
        capture = capture_audit(attempt, case_id)
    review = json.loads(review_path.read_text())
    physical = json.loads(physical_path.read_text())
    result = assess(case_id, capture, review, physical,
                    diagnostic=diagnostic_fixture, attempt=attempt)
    result['pixel_review_sha256'] = sha(review_path)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--physical', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.review, args.physical,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))
