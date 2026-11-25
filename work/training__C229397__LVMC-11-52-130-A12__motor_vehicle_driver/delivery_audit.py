"""Independent saved-source and physical-review audit for crosswalk cases.

Diagnostic mode checks the software join. Original mode requires independent
review of pixels, marking, motion, and every statutory context source.
"""
import argparse
import hashlib
import json
from pathlib import Path

from source_review import FIELDS, join

ASSIGNMENT = 'training__C229397__LVMC-11-52-130-A12__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('vehicle-poses.jsonl', 'control-intent.jsonl', 'video_frames.jsonl',
           'crosswalk-inventory.json', 'crosswalk-source-review.json', 'trace.jsonl')
REVIEW_FLAGS = ('actual_pixels_reviewed', 'marked_crosswalk_reviewed',
                'physical_stop_stand_park_reviewed', 'physical_completion_reviewed',
                'traffic_conflict_reviewed', 'law_compliance_reviewed',
                'police_or_device_directions_reviewed')


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines() if row]


def audit(case, attempt, processing_path, diagnostic=False, review_path=None):
    attempt = Path(attempt).resolve()
    processing = read(processing_path)
    require(case.startswith(ASSIGNMENT + '__') and
            case.rsplit('__', 1)[-1] in
            {'controlled_1', 'controlled_2', 'boundary_20ft', 'stop_near', 'stand_near'},
            'Selected crosswalk case differs')
    require(processing.get('format') == 'worker-saved-processing' and
            processing.get('case_id') == case and processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('candidate_id') == 'primary' and
            processing.get('missing_evidence') is False,
            'Recorded-only processing or selected case differs')
    require(processing.get('physical_acceptance_claimed') is False and
            processing.get('legal_acceptance_claimed') is False,
            'Saved processing crossed acceptance boundary')
    joins = processing.get('timestamp_joins', {})
    require(joins.get('passed') is True and joins.get('frames') == 600,
            'Original saved frame join incomplete')
    source_hashes = processing.get('original_source_hashes', {})
    for name in SOURCES:
        require((attempt / name).is_file() and source_hashes.get(name) == sha(attempt / name),
                'Original source missing or stale: ' + name)
    config = read(attempt / 'config.json')
    require(config.get('case_id') == case and config.get('selected_case_id') == case,
            'Original config case identity differs')
    poses, mapping, controls = (rows(attempt / name) for name in
                                ('vehicle-poses.jsonl', 'video_frames.jsonl',
                                 'control-intent.jsonl'))
    require(len(poses) == len(mapping) == len(controls) == 600,
            'Original subject, camera, or control stream incomplete')
    for i, (pose, frame, control) in enumerate(zip(poses, mapping, controls)):
        require(pose.get('video_frame') == frame.get('video_frame') ==
                control.get('video_frame') == i and
                pose.get('native_frame') == frame.get('native_frame') ==
                control.get('native_frame') and
                abs(pose.get('time_s', -1) - frame.get('time_s', -2)) <= .005 and
                abs(control.get('time_s', -1) - frame.get('time_s', -2)) <= .005 and
                set(frame.get('camera_native_frames', {})) == set(CAMERAS) and
                all(frame['camera_native_frames'][name] == pose['native_frame']
                    for name in CAMERAS),
                'Original source frame or four-camera join differs')
    inventory = read(attempt / 'crosswalk-inventory.json')
    require(inventory.get('source_kind') == 'native_saved_sample',
            'Original Native crosswalk inventory required')
    _, review_sha, findings = join(attempt, inventory)
    require(source_hashes['crosswalk-source-review.json'] == review_sha,
            'Independent context review changed after processing')
    result_path = Path(processing.get('result', ''))
    require(result_path.is_file() and sha(result_path) == processing.get('result_sha256'),
            'Saved result missing or stale')
    result = read(result_path)
    require(result.get('case_id') == case and result.get('accepted') is False and
            result.get('legal_verdict_claimed') is False and
            result.get('video_frame_map_reference') == 'video_frames.jsonl' and
            result.get('behavior_attempted') is True and
            len(result.get('target_checks', [])) == 1 and
            result['target_checks'][0].get('matched') is True,
            'Saved crosswalk measurement or acceptance boundary differs')
    require(processing.get('final_video_checks', {}).get('passed') is True and
            processing['final_video_checks'].get('frames') == 600,
            'Full final video decode missing')
    original_complete = False
    if not diagnostic:
        from worker_exchange import media

        version = Path(processing.get('version', ''))
        for i, camera in enumerate(CAMERAS):
            video_name = camera + '.mkv'
            video_path = attempt / video_name
            decode_path = version / ('source-' + str(i) + '.json')
            require(video_path.is_file() and
                    source_hashes.get(video_name) == sha(video_path) and
                    decode_path.is_file(),
                    'Original camera or source decode receipt missing: ' + camera)
            decode = read(decode_path)
            require(decode.get('format') == 'source-decode' and
                    decode.get('passed') is True and
                    decode.get('frames') == 600 and
                    decode.get('video_sha256') == sha(video_path) and
                    decode.get('mapping_sha256') == sha(attempt / 'video_frames.jsonl') and
                    decode.get('auditor_sha256') == sha(media.__file__),
                    'Original source decode receipt stale: ' + camera)
        require(review_path is not None, 'Original physical review required')
        review = read(review_path)
        require(review.get('case_id') == case and
                review.get('source_hashes') == {name: source_hashes[name] for name in SOURCES},
                'Original physical review binds another source')
        require(all(review.get(flag) is True for flag in REVIEW_FLAGS),
                'Actual pixels, motion, marking, or statutory context review incomplete')
        require(set(findings) == set(FIELDS) and
                all(value != 'unresolved' for value in findings.values()),
                'Original statutory context findings remain unresolved')
        original_complete = True
    return {'format': 'c229397-delivery-audit-v1', 'case_id': case,
            'passed': True, 'diagnostic_fixture': diagnostic,
            'original_source_frame_count': 600,
            'context_review_sha256': review_sha,
            'original_review_complete': original_complete,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--processing', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--review')
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    report = audit(args.case, args.attempt, args.processing, args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, sort_keys=True))
