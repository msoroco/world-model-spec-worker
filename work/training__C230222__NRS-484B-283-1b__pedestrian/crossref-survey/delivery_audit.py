"""Independent source-bound survey delivery audit; original review is mandatory."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FEATURE_CHECKS = {
    '060a': ('crosswalk_paint_pixels_reviewed', 'pedestrian_crossing_path_reviewed',
             'vehicle_right_of_way_reviewed', 'designated_place_reviewed'),
    '060b': ('overhead_or_tunnel_pixels_reviewed', 'pedestrian_access_reviewed',
             'vehicle_right_of_way_reviewed', 'designated_place_reviewed'),
    '140b': ('cane_pixels_reviewed', 'pedestrian_blindness_reviewed',
             'driver_precautions_reviewed'),
    '46': ('school_warning_pixels_reviewed', 'warning_operation_reviewed',
           'child_context_reviewed', 'fifty_foot_stop_and_release_reviewed'),
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing source: ' + path.name)
    return json.loads(path.read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def original_review(code, case, attempt, path):
    if path is None:
        raise ValueError('Original Native source required')
    review = read(path)
    capture = attempt / 'native-capture-report.json'
    native_road = attempt / 'native-road.xodr'
    context = attempt / 'curb-context.json'
    require(review.get('case_id') == case and
            review.get('provenance') == 'original_native' and
            isinstance(review.get('reviewer'), str) and review['reviewer'].strip() and
            review.get('native_capture_report_sha256') == sha(capture) and
            review.get('native_road_sha256') == sha(native_road) and
            review.get('curb_context_sha256') == sha(context),
            'Original Native review source binding differs')
    report = read(capture)
    road_context = read(context)
    require(report.get('case_id') == case and report.get('frames') == 600 and
            report.get('error') is None and report.get('restoration') and
            road_context.get('source_kind') == 'native_observation' and
            road_context.get('native_road_sha256') == sha(native_road) and
            road_context.get('authored_road_sha256') == sha(attempt / 'road.xodr'),
            'Complete restored Native survey capture required')
    for name in (*FEATURE_CHECKS[code], 'physical_completion_reviewed',
                 'vehicle_response_reviewed', 'driver_yield_capability_reviewed'):
        require(review.get(name) is True, 'Original survey source review missing: ' + name)
    frames = review.get('reviewed_frames')
    require(isinstance(frames, list) and frames and
            all(type(x) is int and 0 <= x < 600 for x in frames),
            'Original reviewed frames required')
    hashes = review.get('source_video_sha256')
    require(isinstance(hashes, dict) and set(hashes) == set(CAMERAS),
            'Four original camera hashes required')
    for camera in CAMERAS:
        video = attempt / (camera + '.mkv')
        require(sha(video) == hashes[camera], 'Original survey video changed: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams',
                                'v:0', '-show_entries', 'stream=nb_read_frames', '-of',
                                'default=nokey=1:noprint_wrappers=1', str(video)],
                               capture_output=True, text=True, check=True)
        require(probe.stdout.strip() == '600', 'Original survey video incomplete: ' + camera)
    return {'case_id': case, 'review_sha256': sha(path), 'reviewed_frames': frames,
            'native_road_sha256': sha(native_road), 'source_video_sha256': hashes}


def audit(code, case, candidate, attempt, processing, review, diagnostic):
    require(code in FEATURE_CHECKS, 'Exact survey code required')
    manifest = read(ASSIGNMENT / f'crossref-{code}-manifest.json')
    entries = [x for x in manifest['cases'] if x['case_id'] == case]
    require(len(entries) == 1, 'Exact survey case required')
    entry = entries[0]
    selected = entry if candidate == 'primary' else next(
        (x for x in entry['candidates'] if x['id'] == candidate), None)
    require(selected is not None, 'Exact survey candidate required')
    attempt = Path(attempt)
    saved = read(processing)
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    require(saved.get('passed') is True and saved.get('recorded_only') is True and
            saved.get('originals_preserved') is True and
            saved.get('case_id') == case and saved.get('candidate_id') == candidate and
            saved.get('native_revision', {}).get('construction_sha256') == selected['construction_sha256'] and
            saved.get('timestamp_joins', {}).get('frames') == 600 and
            saved.get('final_video_checks', {}).get('frames') == 600 and
            not saved.get('physical_acceptance_claimed') and
            not saved.get('legal_acceptance_claimed') and
            result.get('case_id') == case and result.get('accepted') is False and
            analysis.get('case_id') == case,
            'Survey saved source or frame join differs')
    measurement = analysis['measurements']['curb_departure_conditional_margin']['value']
    require(measurement.get('original_frames') == 600 and
            measurement.get('impossibility_to_yield_proven') is False and
            measurement.get('legal_verdict_claimed') is False,
            'Survey conditional curb measurement differs')
    if diagnostic:
        compatibility = read(attempt / 'compatibility.json')
        require(compatibility.get('passed') is True and
                compatibility.get('case_id') == case and
                compatibility.get('candidate_id') == candidate and
                compatibility.get('construction_sha256') == selected['construction_sha256'] and
                compatibility.get('negative_removed') == 'curb-samples.jsonl' and
                compatibility.get('negative_log_sha256') == sha(attempt / 'negative-analysis.log') and
                measurement.get('source_kind') == 'synthetic_scene_request',
                'Survey diagnostic source binding differs')
        physical = None
    else:
        physical = original_review(code, case, attempt, review)
        require(result.get('provenance_kind') == 'native_observation' and
                result.get('maneuver_completed') is True,
                'Original Native survey completion required')
    return {'format': 'c230222-survey-source-bound-delivery-audit-v1',
            'case_id': case, 'candidate_id': candidate,
            'construction_sha256': selected['construction_sha256'],
            'processing_sha256': sha(processing),
            'analysis_sha256': sha(attempt / 'analysis-report.json'),
            'physical_review': physical, 'diagnostic_only': diagnostic,
            'physical_or_legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--code', choices=tuple(FEATURE_CHECKS), required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--candidate', default='primary')
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--processing', type=Path, required=True)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    outcome = audit(args.code, args.case, args.candidate, args.attempt,
                    args.processing, args.review, args.diagnostic)
    if args.output.exists():
        raise ValueError('Audit output already exists')
    args.output.write_text(json.dumps(outcome, indent=2) + '\n')
    print(json.dumps({'passed': True, 'case_id': args.case,
                      'candidate_id': args.candidate, 'diagnostic_only': args.diagnostic}))
