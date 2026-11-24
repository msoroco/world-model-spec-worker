"""Independent source-bound review for a future original C104393 delivery.

This audit deliberately rejects the CPU fixture. It requires original Native
sources and a separate, source-hashed visual and physical review after capture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange import media

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')
PHYSICAL_FLAGS = ('vehicle_and_driver_observed', 'other_vehicle_observed',
                  'highway_and_other_area_reviewed', 'continuous_signal_observed',
                  'course_change_observed', 'hill_crest_context_observed')
PIXEL_CLAIMS = ('vehicle', 'other_vehicle', 'signal', 'course_change',
                'road_reference', 'hill_crest')


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    path = Path(path)
    require(path.is_file(), 'Missing delivery source: ' + str(path))
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path != root and root in path.parents and path.is_file(),
            'Delivery source escapes or is missing: ' + str(relative))
    return path


def check_joins(rows, native, trace):
    require(len(rows) == len(native) == len(trace) == 840,
            'Original Native/time join count differs')
    for index, (frame, sample, motion) in enumerate(zip(rows, native, trace)):
        require(frame.get('video_frame') == index and
                frame.get('native_frame') == sample.get('native_frame') == motion.get('frame') and
                abs(frame.get('time_s', -100) - sample.get('time_s', -200)) < 1e-6 and
                abs(frame.get('time_s', -100) - motion.get('time_s', -200)) < 1e-6,
                'Original Native/time join differs')


def check_review(review, case, hashes, dimensions, source_kind):
    require(review.get('format') == 'c104393-independent-original-review-v1' and
            review.get('case_id') == case and review.get('source_kind') == source_kind and
            review.get('legal_verdict') is None,
            'Independent review identity or provenance missing')
    review_hashes = review.get('source_hashes', {})
    for name, digest in hashes.items():
        require(review_hashes.get(name) == digest,
                'Independent review has missing or stale source: ' + name)
    require(set(CHECKS) <= set(review.get('checks', [])),
            'Independent review omits delivery checks')
    physical = review.get('physical_completion', {})
    for flag in PHYSICAL_FLAGS:
        require(physical.get(flag) is True, 'Physical completion review missing: ' + flag)
    require(type(review.get('measured_signal_distance_ft')) in (int, float) and
            abs(review['measured_signal_distance_ft'] - int(case.split('__')[-1])) <= 0.5,
            'Independent measured signal distance differs')
    context = review.get('fixed_context', {})
    require(isinstance(context, dict) and
            context.get('area_classification') == 'any_other_area' and
            context.get('weather') == 'clear_noon' and
            context.get('actor') == 'motor_vehicle_driver' and
            context.get('cell_geometry') == 'hill_crest' and
            isinstance(context.get('other_vehicle_route'), str) and
            bool(context['other_vehicle_route']),
            'Independent fixed context review incomplete')
    boxes = review.get('pixel_boxes', [])
    require({x.get('claim') for x in boxes} >= set(PIXEL_CLAIMS),
            'Independent visual review omits required features')
    for box in boxes:
        source = box.get('source')
        rect = box.get('rect_xywh')
        require(source in CAMERAS and isinstance(box.get('frame'), int) and
                0 <= box['frame'] < 840 and isinstance(rect, list) and len(rect) == 4 and
                all(type(x) is int and x >= 0 for x in rect) and rect[2] > 0 and rect[3] > 0,
                'Reviewed pixel box invalid')
        width, height = dimensions[source]
        require(rect[0] + rect[2] <= width and rect[1] + rect[3] <= height,
                'Reviewed pixel box exceeds source video')


def audit(case, attempt, processing, review, manifest):
    attempt, processing = Path(attempt), Path(processing)
    review_path = Path(review)
    review = read(review_path)
    receipt = read(processing)
    manifest = read(manifest)
    entry = next((x for x in manifest['cases'] if x['case_id'] == case), None)
    require(entry is not None and entry['kind'] == 'delivery', 'Exact selected case missing')
    require(receipt.get('case_id') == case and receipt.get('candidate_id') == 'primary' and
            receipt.get('passed') is True and receipt.get('recorded_only') is True and
            receipt.get('missing_evidence') is False and
            receipt.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256'],
            'Saved processing or construction differs')
    require(not receipt.get('physical_acceptance_claimed') and
            not receipt.get('legal_acceptance_claimed'),
            'Saved processor preempted independent review')
    native_manifest = read(attempt / 'capture/manifest.json')
    require(native_manifest.get('synthetic_diagnostic') is not True,
            'Synthetic diagnostic cannot be original delivery')
    native_report = read(attempt / 'native-capture-report.json')
    road_geometry = read(attempt / 'road_geometry.json')
    require(native_manifest.get('frames') == 840 and
            native_report.get('case_id') == case and native_report.get('candidate_id') == 'primary' and
            native_report.get('frames') == 840 and native_report.get('error') is None and
            road_geometry.get('provenance') == 'original_native_capture',
            'Original Native provenance and frame count required')
    required = ['native_samples.jsonl', 'body_history.jsonl', 'trace.jsonl',
                'video_frames.jsonl', 'road.xodr', 'road_geometry.json',
                'native-capture-report.json', 'capture/manifest.json',
                'capture/native/frames.jsonl', *(name + '.mkv' for name in CAMERAS)]
    hashes = receipt.get('original_source_hashes', {})
    for name in required:
        path = checked_path(attempt, name)
        require(hashes.get(name) == sha(path), 'Missing or stale original source: ' + name)
    rows = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    native = [json.loads(line) for line in (attempt / 'native_samples.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    construction = read(HERE / entry['construction'])
    config = json.loads(next(x['content'] for x in construction['files']
                             if x['path'] == 'config.json'))
    dimensions = {x['name']: (x['width'], x['height']) for x in config['cameras']}
    check_joins(rows, native, trace)
    check_review(review, case, {name: hashes[name] for name in required},
                 dimensions, 'original_native')
    version = Path(receipt['version'])
    raw = checked_path(version, 'analysis/raw.mkv')
    media.verify_receipt(raw, receipt['final_video_checks'], 840)
    return {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
            'checks': list(CHECKS), 'original_native': True,
            'processing_sha256': sha(processing), 'review_sha256': sha(review_path),
            'source_hashes': {name: hashes[name] for name in required},
            'measured_signal_distance_ft': review['measured_signal_distance_ft'],
            'fixed_context': review.get('fixed_context'),
            'physical_acceptance_claimed': False, 'legal_verdict': None}


def selftest(case, negative=False):
    entry = next((x for x in read(HERE / 'execution-manifest.json')['cases']
                  if x['case_id'] == case), None)
    require(entry is not None and entry['kind'] == 'delivery', 'Exact selected case missing')
    feet = int(case.split('__')[-1])
    spec = read(HERE / f'current-{feet}-graph.json')
    receipt_name = f'current-active-{feet}-primary-saved-receipt.json'
    receipt = read(HERE / receipt_name)
    require(receipt.get('passed') is True and receipt.get('case_id') == case and
            receipt.get('native_revision', {}).get('construction_sha256') == entry['construction_sha256'],
            'Selected synthetic source-shaped receipt differs')
    decode = receipt.get('final_video_checks', {})
    require(decode.get('format') == 'source-decode' and decode.get('passed') is True and
            decode.get('frames') == 840 and
            decode.get('auditor_sha256') == sha(Path(media.__file__)) and
            decode.get('checks', {}).get('frame_count') == 'all-decoded-frames',
            'Current full-decode mechanics receipt missing')
    sources = receipt['original_source_hashes']
    for name, content in spec['files'].items():
        require(sources.get(name) == hashlib.sha256(content.encode()).hexdigest(),
                'Source-shaped diagnostic bytes differ: ' + name)
    rows = [[json.loads(line) for line in spec['files'][name].splitlines()]
            for name in ('video_frames.jsonl', 'native_samples.jsonl', 'trace.jsonl')]
    check_joins(*rows)
    dimensions = {x['path'].removesuffix('.mkv'): (x['width'], x['height'])
                  for x in spec['videos']}
    core = ('native_samples.jsonl', 'trace.jsonl', 'video_frames.jsonl',
            *(name + '.mkv' for name in CAMERAS))
    review = {'format': 'c104393-independent-original-review-v1', 'case_id': case,
              'source_kind': 'synthetic_cpu_mechanics', 'legal_verdict': None,
              'source_hashes': {name: sources[name] for name in core},
              'checks': list(CHECKS), 'physical_completion': {flag: True for flag in PHYSICAL_FLAGS},
              'measured_signal_distance_ft': feet,
              'fixed_context': {'area_classification': 'any_other_area',
                                'weather': 'clear_noon', 'actor': 'motor_vehicle_driver',
                                'cell_geometry': 'hill_crest',
                                'other_vehicle_route': 'source-shaped diagnostic route'},
              'pixel_boxes': [{'claim': claim, 'source': CAMERAS[i % 4],
                               'frame': i, 'rect_xywh': [0, 0, 4, 4]}
                              for i, claim in enumerate(PIXEL_CLAIMS)]}
    if negative:
        review['pixel_boxes'][0]['rect_xywh'][0] = dimensions['overview'][0]
    check_review(review, case, {name: sources[name] for name in core},
                 dimensions, 'synthetic_cpu_mechanics')
    require(not negative, 'Negative mechanics did not reject')
    return {'passed': True, 'case_id': case, 'scope': 'synthetic source-shaped mechanics only',
            'original_native_observed': False, 'physical_acceptance_claimed': False,
            'source_hashes_checked': len(spec['files']), 'joined_frames': 840}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--processing')
    parser.add_argument('--review')
    parser.add_argument('--manifest', default=str(HERE / 'execution-manifest.json'))
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        print(json.dumps(selftest(args.case, args.negative_selftest), indent=2))
    else:
        require(args.attempt and args.processing and args.review,
                'Original delivery source paths required')
        print(json.dumps(audit(args.case, args.attempt, args.processing,
                               args.review, args.manifest), indent=2))


if __name__ == '__main__':
    main()
