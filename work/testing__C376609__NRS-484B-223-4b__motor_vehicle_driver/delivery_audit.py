"""Independent original source and four-camera custody audit, no legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

AID = 'testing__C376609__NRS-484B-223-4b__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(case, attempt, review, physical, *, diagnostic_fixture=False):
    attempt, review, physical = Path(attempt), Path(review), Path(physical)
    if not case.startswith(AID + '__'):
        raise ValueError('exact selected case required')
    if diagnostic_fixture:
        capture = json.loads((attempt / 'diagnostic-capture-audit.json').read_text())
        pixels = json.loads(review.read_text())
        measured = json.loads(physical.read_text())
        if capture.get('case_id') != case or capture.get('diagnostic_fixture') is not True or capture.get('frame_count') != 900:
            raise ValueError('diagnostic capture protocol incomplete')
        if pixels.get('case_id') != case or pixels.get('diagnostic_fixture') is not True or pixels.get('capture_sha256') != sha(attempt / 'diagnostic-capture-audit.json'):
            raise ValueError('diagnostic review binding differs')
        views = pixels.get('views')
        if not isinstance(views, dict) or set(views) != set(CAMERAS):
            raise ValueError('independent pixel review missing four views')
        for name in CAMERAS:
            if views[name].get('video_sha256') != capture.get('video_sha256', {}).get(name) or views[name].get('vehicle_visible') is not True:
                raise ValueError('diagnostic view binding incomplete: ' + name)
        if measured.get('case_id') != case or measured.get('diagnostic_fixture') is not True or measured.get('physical_acceptance_claimed') is not False:
            raise ValueError('diagnostic physical proof incomplete')
        return {'format': 'worker-independent-delivery-protocol', 'case_id': case,
                'diagnostic_fixture': True, 'source_verified': False,
                'physical_acceptance_claimed': False, 'legal_verdict': None}
    receipt = json.loads((attempt / 'receipt.json').read_text())
    if receipt.get('case_id') != case or receipt.get('source_kind') != 'original_native_capture' or receipt.get('diagnostic_fixture') is not False:
        raise ValueError('sealed original Native source required')
    if receipt.get('frame_count') != 900 or receipt.get('fps') != 20:
        raise ValueError('complete 900-frame original capture required')
    for name, key in (('context.json', 'context_sha256'), ('original-trace.jsonl', 'trace_sha256'),
                      ('video_frames.jsonl', 'frame_map_sha256')):
        if sha(attempt / name) != receipt.get(key):
            raise ValueError('original source changed: ' + name)
    if set(receipt.get('cameras', {})) != set(CAMERAS):
        raise ValueError('four original cameras required')
    pixel_review = json.loads(review.read_text())
    if pixel_review.get('case_id') != case or pixel_review.get('receipt_sha256') != sha(attempt / 'receipt.json') or not pixel_review.get('reviewer'):
        raise ValueError('independent original pixel review missing')
    views = pixel_review.get('views')
    if not isinstance(views, dict) or set(views) != set(CAMERAS):
        raise ValueError('all four original views must be reviewed')
    for name in CAMERAS:
        video = attempt / receipt['cameras'][name]['path']
        if sha(video) != receipt['cameras'][name]['sha256']:
            raise ValueError('original video changed: ' + name)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                                '-show_entries', 'stream=nb_read_frames', '-of', 'default=noprint_wrappers=1:nokey=1', str(video)],
                               check=True, capture_output=True, text=True)
        if probe.stdout.strip() != '900':
            raise ValueError('original full video decode incomplete: ' + name)
        item = views[name]
        if item.get('video_sha256') != sha(video) or item.get('vehicle_visible') is not True or item.get('lane_and_intersection_visible') is not True:
            raise ValueError('independent original view observation incomplete: ' + name)
    physical_result = json.loads(physical.read_text())
    if physical_result.get('case_id') != case or physical_result.get('diagnostic_fixture') is not False or physical_result.get('physical_checks', {}).get('setup', {}).get('status') != 'met':
        raise ValueError('source-bound original physical setup review missing')
    return {'format': 'worker-independent-original-delivery-audit', 'case_id': case,
            'receipt_sha256': sha(attempt / 'receipt.json'), 'pixel_review_sha256': sha(review),
            'physical_result_sha256': sha(physical), 'source_verified': True,
            'legal_verdict': None, 'canonical_acceptance': False}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    for name in ('case', 'attempt', 'review', 'physical'):
        ap.add_argument('--' + name, required=True)
    ap.add_argument('--diagnostic-fixture', action='store_true')
    args = ap.parse_args()
    print(json.dumps(audit(args.case, args.attempt, args.review, args.physical,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))
