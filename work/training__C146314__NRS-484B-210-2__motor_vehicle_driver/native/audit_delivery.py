"""Independent source-bound delivery audit for a selected right-side pass.

A diagnostic attempt can exercise this audit but cannot produce acceptance.
Original delivery additionally needs independent pixel review and verified motion.
"""
import hashlib
import json
from pathlib import Path

from audit_physical_motion import audit as audit_motion

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('native-raw-actors.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl',
           *(name+'.mkv' for name in CAMERAS))
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def verify_capture_closure(report, case_id, candidate_id):
    require(report.get('case_id') == case_id and
            report.get('candidate_id') == candidate_id and
            report.get('observed_frames') == 240 and
            report.get('error') is None and
            report.get('closure_failures') == [] and
            report.get('lifecycle_events') ==
            ['capture_finished','encoders_closed','restoration_verified'] and
            report.get('restoration',{}).get('restored') is True,
            'Original Native ownership closure or world restoration unverified')


def audit(attempt, processing, case_id, candidate_id, pixel_review=None):
    attempt = Path(attempt)
    require(processing.get('case_id') == case_id and
            processing.get('candidate_id') == candidate_id and
            processing.get('passed') is True and processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('missing_evidence') is False,
            'Saved processing does not bind selected case and candidate')
    hashes = processing.get('original_source_hashes', {})
    require(all(name in hashes and (attempt/name).is_file() and
                sha(attempt/name) == hashes[name] for name in SOURCES),
            'Original delivery sources changed or are missing')
    require(processing.get('timestamp_joins', {}).get('passed') is True and
            processing['timestamp_joins'].get('frames') == 240 and
            processing.get('final_video_checks', {}).get('passed') is True and
            processing['final_video_checks'].get('frames') == 240,
            'Delivery joins or primary video decode missing')
    result = read(processing['result'])
    require(result.get('case_id') == case_id and
            sha(processing['result']) == processing.get('result_sha256') and
            result.get('accepted') is False,
            'Saved right-pass result differs')
    motion = audit_motion(attempt)
    if motion['source_kind'] == 'synthetic_native_sample':
        require(pixel_review is None and motion['status'] == 'unverified' and
                result.get('provenance_kind') == 'synthetic_local_diagnostic' and
                not processing.get('physical_acceptance_claimed') and
                not processing.get('legal_acceptance_claimed'),
                'Diagnostic source claimed original delivery')
        return {'format':'c146314-delivery-audit-v1', 'case_id':case_id,
                'candidate_id':candidate_id, 'passed':False,
                'source_shape_passed':True, 'checks':{name:False for name in CHECKS},
                'physical_or_legal_acceptance_claimed':False}
    require((attempt/'native-capture-report.json').is_file(),
            'Original Native capture report missing')
    capture_report = read(attempt/'native-capture-report.json')
    verify_capture_closure(capture_report,case_id,candidate_id)
    require(motion['source_kind'] == 'original_native' and motion['status'] == 'met' and
            result.get('provenance_kind') == 'native' and result.get('maneuver_completed') is True and
            pixel_review is not None,
            'Original physical completion or pixel review missing')
    review = read(pixel_review)
    require(review.get('format') == 'c146314-original-pixel-review-v1' and
            review.get('case_id') == case_id and review.get('source_kind') ==
            'original_native_camera_pixels' and review.get('reviewer') and
            review.get('method') and review.get('frame_map_sha256') ==
            hashes['video_frames.jsonl'] and review.get('legal_verdict_claimed') is False,
            'Independent original pixel review missing or changed')
    views = review.get('views', {})
    require(set(views) == set(CAMERAS), 'Pixel review omits a source camera')
    saved_dir = Path(processing['result']).parent.parent
    visible = set()
    for index, name in enumerate(CAMERAS):
        item = views[name]
        decoded = read(saved_dir/f'source-{index}.json')
        require(item.get('video_sha256') == hashes[name+'.mkv'] and
                item.get('reviewed_frame_ids') == list(range(240)) and
                decoded.get('passed') is True and decoded.get('frames') == 240 and
                decoded.get('video_sha256') == hashes[name+'.mkv'] and
                item.get('rgb_sequence_sha256') == decoded.get('rgb_sequence_sha256') and
                item.get('limitations') is not None,
                'Original decoded pixel review changed: '+name)
        visible.update(item.get('subjects_visible', []))
    require({'ego_body', 'lead_body', 'right_lane', 'roadway'} <= visible,
            'Original pixels do not establish the right-pass scene')
    return {'format':'c146314-delivery-audit-v1', 'case_id':case_id,
            'candidate_id':candidate_id, 'passed':True,
            'checks':{name:True for name in CHECKS},
            'source_hashes':{name:hashes[name] for name in SOURCES},
            'pixel_review_sha256':sha(pixel_review),
            'delivery_accepted':True,
            'legal_safety_verdict':None}
