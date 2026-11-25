"""Independent source-bound audit for one prospective C111071 delivery case."""
import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('candidate-selection.json', 'capture/manifest.json', 'native_samples.jsonl',
           'road_geometry.json', 'video_frames.jsonl', 'trace.jsonl',
           *(name + '.mkv' for name in CAMERAS))
NATIVE_REVIEW_SOURCES = ('native_raw_readback.jsonl', 'map-import-survey.json',
                         'source-review.json')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(case, candidate, attempt, processing, diagnostic=False):
    manifest = read(ROOT / 'execution-manifest.json')
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unselected delivery case')
    selected = entry if candidate == 'primary' else next(
        (item for item in entry.get('candidates', []) if item['id'] == candidate), None)
    if selected is None or sha(ROOT / selected['construction']) != selected['construction_sha256']:
        raise ValueError('Selected construction changed')
    selection = read(attempt / 'candidate-selection.json')
    if (selection.get('case_id') != case or selection.get('candidate_id') != candidate
            or selection.get('construction_sha256') != selected['construction_sha256']):
        raise ValueError('Candidate selection differs')
    receipt = read(processing)
    if (receipt.get('case_id') != case or receipt.get('candidate_id') != candidate
            or receipt.get('passed') is not True or receipt.get('recorded_only') is not True
            or receipt.get('originals_preserved') is not True or receipt.get('missing_evidence')
            or receipt.get('timestamp_joins', {}).get('frames') != 600
            or receipt.get('final_video_checks', {}).get('passed') is not True
            or receipt.get('final_video_checks', {}).get('frames') != 600
            or receipt.get('physical_acceptance_claimed') or receipt.get('legal_acceptance_claimed')):
        raise ValueError('Saved source proof incomplete')
    hashes = {}
    for source in SOURCES:
        path = attempt / source
        if not path.is_file():
            raise ValueError('Missing original source: ' + source)
        hashes[source] = sha(path)
        if receipt.get('original_source_hashes', {}).get(source) != hashes[source]:
            raise ValueError('Saved original source changed: ' + source)
    samples = rows(attempt / 'native_samples.jsonl')
    frames = rows(attempt / 'video_frames.jsonl')
    if len(samples) != 600 or len(frames) != 600 or any(
            sample['native_frame'] != frame['native_frame']
            or sample['native_frame'] != frame['carla_frame']
            or abs(sample['time_s'] - frame['time_s']) > 1e-8
            or frame['video_frame'] != index
            for index, (sample, frame) in enumerate(zip(samples, frames))):
        raise ValueError('Original source frame join differs')
    if any(sample.get('actor_class_observed') != 'motorcycle'
           or not sample.get('body_vertices_m')
           or sample.get('ego_face_observed') != 'circular_red_green_left_arrow'
           for sample in samples):
        raise ValueError('Motorcycle, body or governing face source differs')
    road = read(attempt / 'road_geometry.json')
    if road.get('governing_face') != 'circular_red_green_left_arrow' or not road.get('approach_enters_intersection'):
        raise ValueError('Road and signal source differs')
    result_path = Path(receipt['result'])
    if not result_path.is_file() or sha(result_path) != receipt.get('result_sha256'):
        raise ValueError('Saved result changed')
    result = read(result_path)
    if result.get('case_id') != case or result.get('accepted') or result.get('legal_verdict_claimed'):
        raise ValueError('Saved result identity or acceptance differs')
    common = {'format': 'c111071-delivery-audit', 'case_id': case,
              'candidate_id': candidate, 'original_source_sha256': hashes,
              'source_kind': read(attempt / 'capture/manifest.json').get('source_kind')}
    if diagnostic:
        return {**common, 'diagnostic_only': True, 'accepted': False,
                'checks': {key: key in ('time_join', 'full_video_decode') for key in CHECKS},
                'original_native_verified': False, 'actual_pixels_verified': False}
    if common['source_kind'] != 'original_native' or selection.get('manifest_sha256') != sha(ROOT / 'execution-manifest.json'):
        raise ValueError('Original Native source required')
    for source in NATIVE_REVIEW_SOURCES:
        path = attempt / source
        if not path.is_file():
            raise ValueError('Missing original source: ' + source)
        hashes[source] = sha(path)
        if receipt.get('original_source_hashes', {}).get(source) != hashes[source]:
            raise ValueError('Saved original source changed: ' + source)
    review = read(attempt / 'source-review.json')
    reviewed_sources = ('native_raw_readback.jsonl', 'video_frames.jsonl',
                        'map-import-survey.json', *(name + '.mkv' for name in CAMERAS))
    if (review.get('review_kind') != 'original_source_review'
            or not isinstance(review.get('reviewer'), str)
            or not review['reviewer'].strip()
            or review.get('source_sha256') != {source: hashes[source]
                                                for source in reviewed_sources}
            or road.get('original_source_sha256') != review['source_sha256']
            or road.get('review_sha256') != hashes['source-review.json']):
        raise ValueError('Original source review missing or stale')
    review_path = attempt / 'independent-physical-review.json'
    if not review_path.is_file():
        raise ValueError('Independent physical and pixel review required')
    review = read(review_path)
    if (review.get('case_id') != case or review.get('candidate_id') != candidate
            or review.get('source_hashes') != hashes or review.get('passed') is not True
            or any(review.get(key) is not True for key in (
                'governing_signal_pixels_verified', 'detector_cause_verified',
                'stop_and_two_cycle_history_verified', 'other_device_survey_verified',
                'lawful_pedestrian_and_traffic_yield_verified', 'full_body_and_motion_verified'))):
        raise ValueError('Independent statutory source review incomplete')
    return {**common, 'diagnostic_only': False, 'accepted': True,
            'checks': {key: True for key in CHECKS}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('case', 'candidate', 'attempt', 'processing', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    value = audit(args.case, args.candidate, Path(args.attempt), Path(args.processing), args.diagnostic)
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain previous audit output')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'case_id': args.case, 'diagnostic_only': args.diagnostic,
                      'accepted': value['accepted']}))
