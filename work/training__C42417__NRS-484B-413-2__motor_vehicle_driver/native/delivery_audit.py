"""Independent C42417 source and visual review; CPU fixture is mechanics only."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from physical_preparation import assess as assess_physical

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
SOURCES = ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl',
           'trace.jsonl', 'road.xodr', 'road_geometry.json', 'control_context.json',
           'capture/evidence.jsonl', 'capture/native/frames.jsonl',
           'capture/manifest.json') + tuple(name + '.mkv' for name in CAMERAS)


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def check_join(mapping, native, trace):
    require(len(mapping) == len(native) == len(trace) == 600,
            'Original 600-frame Native/time join differs')
    for i, (frame, sample, motion) in enumerate(zip(mapping, native, trace)):
        require(frame['video_frame'] == i and
                frame['native_frame'] == sample['native_frame'] == motion['frame'] and
                abs(frame['time_s'] - sample['time_s']) < 1e-6 and
                abs(frame['time_s'] - motion['time_s']) < 1e-6,
                'Original Native/time join differs')


def check_review(review, case, hashes, dimensions, source_kind):
    require(review.get('format') == 'c42417-independent-review-v1' and
            review.get('case_id') == case and review.get('source_kind') == source_kind and
            review.get('legal_verdict') is None,
            'Independent review identity or provenance differs')
    for name, digest in hashes.items():
        require(review.get('source_hashes', {}).get(name) == digest,
                'Independent review source is stale: ' + name)
    require(set(CHECKS) <= set(review.get('checks', [])),
            'Independent delivery checks missing')
    require(review.get('physical_completion') is True and
            review.get('business_district_reviewed') is True and
            review.get('right_indicator_pixels_reviewed') is True and
            review.get('course_change_reviewed') is True,
            'Original physical or visual review incomplete')
    boxes = review.get('pixel_boxes', [])
    require({'vehicle', 'right_indicator', 'course_change', 'business_district'} <=
            {box.get('claim') for box in boxes}, 'Original pixel claims missing')
    for box in boxes:
        camera = box.get('source')
        rect = box.get('rect_xywh')
        require(camera in CAMERAS and isinstance(box.get('frame'), int) and
                0 <= box['frame'] < 600 and isinstance(rect, list) and len(rect) == 4 and
                all(type(value) is int and value >= 0 for value in rect) and
                rect[2] > 0 and rect[3] > 0,
                'Reviewed pixel box invalid')
        width, height = dimensions[camera]
        require(rect[0] + rect[2] <= width and rect[1] + rect[3] <= height,
                'Reviewed pixel box exceeds source video')


def decoded_frames(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-count_frames', '-show_entries', 'stream=nb_read_frames,width,height',
        '-of', 'json', str(path)], capture_output=True, text=True, check=True,
        timeout=90)
    stream = json.loads(result.stdout)['streams'][0]
    require(int(stream['nb_read_frames']) == 600, 'Full source video decode differs')
    return int(stream['width']), int(stream['height'])


def audit(case, attempt, review_path):
    attempt = Path(attempt).resolve()
    manifest = read(FOLDER / 'execution-manifest.json')
    require(any(entry['case_id'] == case for entry in manifest['cases']),
            'Selected case absent from manifest')
    capture = read(attempt / 'capture/manifest.json')
    require(capture.get('synthetic_diagnostic') is not True and
            capture.get('frames') == 600,
            'Synthetic diagnostic cannot be original delivery')
    geometry = read(attempt / 'road_geometry.json')
    require(geometry.get('provenance') == 'original_native_capture',
            'Original Native road provenance required')
    hashes = {}
    for name in SOURCES:
        path = (attempt / name).resolve()
        require(attempt in path.parents and path.is_file(),
                'Missing original source: ' + name)
        hashes[name] = sha(path)
    check_join(*(rows(attempt / name) for name in
                 ('video_frames.jsonl', 'native_samples.jsonl', 'trace.jsonl')))
    physical = assess_physical(attempt)
    require(physical['status'] == 'met',
            'Original source-derived physical completion not established')
    dimensions = {name: decoded_frames(attempt / (name + '.mkv'))
                  for name in CAMERAS}
    review_path = Path(review_path)
    check_review(read(review_path), case, hashes, dimensions, 'original_native')
    return {'format': 'worker-delivery-audit', 'case_id': case,
            'checks': list(CHECKS), 'passed': True,
            'source_hashes': hashes, 'review_sha256': sha(review_path),
            'physical_acceptance_claimed': False, 'legal_verdict': None}


def selftest(case, negative):
    suffix = case.rsplit('_', 1)[-1]
    require(suffix in ('a', 'b', 'c'), 'Unknown case')
    spec = read(HERE / f'selected-{suffix}-fixture.json')
    receipt = read(HERE / f'selected-{suffix}-primary-compatibility.json')
    require(receipt['case_id'] == case and receipt['passed'] is True and
            {'final_decode', 'selected_measurements', 'negative_case_source'} <=
            set(receipt['checks']), 'Selected compatibility mechanics missing')
    hashes = {}
    for name in ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl',
                 'trace.jsonl', 'road.xodr', 'road_geometry.json',
                 'control_context.json', 'capture/evidence.jsonl'):
        digest = hashlib.sha256(spec['files'][name].encode()).hexdigest()
        require(receipt['fixture_manifest'].get(name) == digest,
                'Selected source-shaped fixture changed: ' + name)
        hashes[name] = digest
    mapping, native, trace = ([json.loads(line) for line in spec['files'][name].splitlines()]
        for name in ('video_frames.jsonl', 'native_samples.jsonl', 'trace.jsonl'))
    check_join(mapping, native, trace)
    dimensions = {item['path'].removesuffix('.mkv'): (item['width'], item['height'])
                  for item in spec['videos']}
    review = {'format':'c42417-independent-review-v1', 'case_id':case,
        'source_kind':'synthetic_cpu_mechanics', 'legal_verdict':None,
        'source_hashes':hashes, 'checks':list(CHECKS),
        'physical_completion':True, 'business_district_reviewed':True,
        'right_indicator_pixels_reviewed':True, 'course_change_reviewed':True,
        'pixel_boxes':[{'claim':claim, 'source':CAMERAS[i], 'frame':300+i,
                        'rect_xywh':[0,0,4,4]} for i,claim in
                       enumerate(('vehicle','right_indicator','course_change','business_district'))]}
    if negative:
        review['pixel_boxes'][0]['rect_xywh'][0] = dimensions['overview'][0]
    check_review(review, case, hashes, dimensions, 'synthetic_cpu_mechanics')
    require(not negative, 'Negative mechanics did not reject')
    return {'passed':True,'case_id':case,'scope':'synthetic CPU mechanics only',
            'joined_frames':600,'original_native_observed':False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--review')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.case, args.negative_selftest), sort_keys=True))
    else:
        require(args.attempt and args.review, 'Original delivery source paths required')
        print(json.dumps(audit(args.case, args.attempt, args.review), sort_keys=True))


if __name__ == '__main__':
    main()
