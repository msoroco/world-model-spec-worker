"""Independent, fail-closed original-source delivery acceptance contract.

This is a future Native audit. Synthetic diagnostic processing cannot pass it.
It makes no statutory finding; City and exception sources need separate review.
"""
import hashlib
import json
from pathlib import Path

from measure_saved import measure

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'native-capture-report.json', 'video_frames.jsonl',
           'capture/evidence.jsonl', 'trace.jsonl',
           *(name + '.mkv' for name in CAMERAS))
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(attempt, processing, case_id, candidate_id, pixel_review,
          city_review, exception_review):
    attempt = Path(attempt)
    require(processing.get('case_id') == case_id and
            processing.get('candidate_id') == candidate_id and
            processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False,
            'Saved processing does not bind selected case and candidate')
    hashes = processing.get('original_source_hashes', {})
    require(all(name in hashes and (attempt / name).is_file() and
                sha(attempt / name) == hashes[name] for name in SOURCES),
            'Original delivery sources changed or are missing')
    joins = processing.get('timestamp_joins', {})
    final = processing.get('final_video_checks', {})
    require(joins.get('passed') is True and joins.get('frames') == 600 and
            final.get('passed') is True and final.get('frames') == 600,
            'Delivery joins or final decode missing')
    report = read(attempt / 'native-capture-report.json')
    require(report.get('case_id') == case_id and
            report.get('candidate_id') == candidate_id and
            report.get('observed_frames') == 600 and
            report.get('error') is None and
            report.get('restoration') is not None,
            'Original Native ownership closure or restoration unverified')
    measured = measure(attempt)
    require(measured['source_kind'] == 'original_native' and
            measured['frames'] == 600 and measured['moving_frames'] >= 100,
            'Original participant motion unverified')
    require((measured['moving_sidewalk_overlap_frames'] >= 20 if
             case_id.endswith('__contrast') else
             measured['moving_sidewalk_overlap_frames'] == 0),
            'Selected physical completion not met')
    result_path = Path(processing['result'])
    result = read(result_path)
    require(sha(result_path) == processing.get('result_sha256') and
            result.get('case_id') == case_id and result.get('accepted') is False and
            result.get('provenance_kind') == 'native',
            'Original saved result differs')
    review = read(pixel_review)
    require(review.get('case_id') == case_id and
            review.get('source_kind') == 'original_native_camera_pixels' and
            review.get('reviewer') and review.get('method') and
            review.get('frame_map_sha256') == hashes['video_frames.jsonl'] and
            review.get('legal_verdict_claimed') is False,
            'Independent original pixel review missing')
    require(set(review.get('views', {})) == set(CAMERAS),
            'Pixel review omits a source camera')
    saved_dir = result_path.parent.parent
    visible = set()
    for index, name in enumerate(CAMERAS):
        item = review['views'][name]
        decoded = read(saved_dir / f'source-{index}.json')
        require(item.get('video_sha256') == hashes[name + '.mkv'] and
                item.get('reviewed_frame_ids') == list(range(600)) and
                decoded.get('passed') is True and decoded.get('frames') == 600 and
                decoded.get('video_sha256') == hashes[name + '.mkv'] and
                item.get('rgb_sequence_sha256') == decoded.get('rgb_sequence_sha256'),
                'Original decoded pixel review changed: ' + name)
        visible.update(item.get('subjects_visible', []))
    require({'heavy_vehicle_body', 'roadway', 'sidewalk_boundary'} <= visible,
            'Original pixels do not establish all participants and sidewalk scene')
    city = read(city_review)
    require(city.get('reviewed') is True and city.get('reviewer') and
            city.get('citation') and city.get('city_sidewalk_authority') is True and
            city.get('entrance_authority') is True and
            city.get('map_readback_sha256') == hashes['native-map-readback.json'] and
            city.get('survey_source_sha256') == sha(attempt / 'city-survey-source.geojson') and
            city.get('calibration_sha256') == sha(attempt / 'city-calibration.json'),
            'City sidewalk and entrance authority not source-qualified')
    exception = read(exception_review)
    require(exception.get('reviewed') is True and exception.get('reviewer') and
            exception.get('citation') and
            exception.get('status') == 'reviewed_not_applicable' and
            exception.get('native_capture_report_sha256') == hashes['native-capture-report.json'] and
            exception.get('document_sha256') == sha(attempt / exception['document_path']),
            'Subsection 2 exception facts not source-qualified')
    return {'format': 'c422978-original-delivery-audit-v1',
            'case_id': case_id, 'candidate_id': candidate_id,
            'passed': True, 'checks': {key: True for key in CHECKS},
            'source_hashes': {name: hashes[name] for name in SOURCES},
            'pixel_review_sha256': sha(pixel_review),
            'city_review_sha256': sha(city_review),
            'exception_review_sha256': sha(exception_review),
            'delivery_accepted': True, 'legal_verdict': None}
