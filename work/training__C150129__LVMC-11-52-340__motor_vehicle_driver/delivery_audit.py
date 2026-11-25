"""Independent municipal parking source and lifecycle audit.

Diagnostic mode checks the saved fixture chain. Original mode additionally
requires source-hashed human review of City context, pixels, and maneuver.
Neither mode makes a legal acceptance decision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


ASSIGNMENT = 'training__C150129__LVMC-11-52-340__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SOURCES = ('parking-inventory.json', 'review.json', 'vehicle-poses.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
           'source_context/city_street.txt',
           'source_context/council_designation.txt',
           'source_context/posting_or_marking.txt',
           'source_context/subject_vehicle_status.txt')
REVIEW_FLAGS = ('city_street_reviewed', 'council_designation_reviewed',
                'posting_or_marking_reviewed', 'subject_vehicle_status_reviewed',
                'actual_pixels_reviewed', 'physical_parking_completion_reviewed')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decode(path):
    process = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
        '-select_streams', 'v:0', '-show_entries',
        'stream=codec_name,nb_read_frames,width,height', '-of', 'json', str(path)],
        capture_output=True, text=True, timeout=180)
    require(process.returncode == 0, 'Original camera decode failed: ' + path.name)
    streams = json.loads(process.stdout).get('streams', [])
    require(len(streams) == 1 and streams[0].get('codec_name') == 'ffv1' and
            streams[0].get('nb_read_frames') == '600',
            'Original camera codec or frame count differs: ' + path.name)
    return {key: streams[0].get(key) for key in
            ('codec_name', 'nb_read_frames', 'width', 'height')}


def audit(case, attempt, processing_path, diagnostic=False, review_path=None):
    attempt = Path(attempt)
    processing = read(processing_path)
    require(case in (ASSIGNMENT + '__controlled_1', ASSIGNMENT + '__controlled_2') and
            processing.get('case_id') == case and
            processing.get('candidate_id') == 'primary',
            'Selected municipal case or candidate differs')
    require(processing.get('format') == 'worker-saved-processing' and
            processing.get('passed') is True and
            processing.get('recorded_only') is True and
            processing.get('originals_preserved') is True and
            processing.get('timestamp_joins', {}).get('passed') is True and
            processing['timestamp_joins'].get('frames') == 600,
            'Recorded-only lifecycle or frame join differs')
    require(processing.get('physical_acceptance_claimed') is False and
            processing.get('legal_acceptance_claimed') is False,
            'Saved processor crossed acceptance boundary')
    selected = read(attempt / 'candidate-selection.json')
    require(selected.get('case_id') == case and
            selected.get('candidate_id') == 'primary' and
            selected.get('construction_sha256') == sha(attempt / 'construction.json'),
            'Native selected construction differs')
    source_hashes = processing.get('original_source_hashes', {})
    for name in (*SOURCES, *(camera + '.mkv' for camera in CAMERAS)):
        path = attempt / name
        require(path.is_file() and source_hashes.get(name) == sha(path),
                'Original source missing or stale: ' + name)
    poses = rows(attempt / 'vehicle-poses.jsonl')
    frame_map = rows(attempt / 'video_frames.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    require(len(poses) == len(frame_map) == len(evidence) == 600,
            'Original subject, camera, or capture stream incomplete')
    for index, (pose, frame) in enumerate(zip(poses, frame_map)):
        require(pose.get('video_frame') == frame.get('video_frame') == index and
                pose.get('native_frame') == frame.get('native_frame'),
                'Original subject/camera frame identity differs')
    cameras = {camera: decode(attempt / (camera + '.mkv')) for camera in CAMERAS}
    inventory = read(attempt / 'parking-inventory.json')
    context = read(attempt / 'review.json')
    require(inventory.get('assignment_id') == ASSIGNMENT and
            context.get('case_id') == case and
            context.get('native_inventory_sha256') == sha(attempt / 'parking-inventory.json'),
            'Municipal source review binds another inventory or case')
    for name in ('city_street', 'council_designation', 'posting_or_marking',
                 'subject_vehicle_status'):
        record = context.get(name, {})
        source = attempt / record.get('path', '')
        require(source.is_file() and source_hashes.get(record['path']) ==
                record.get('sha256') == sha(source),
                'Independent municipal context source differs: ' + name)
    result_path = Path(processing.get('result', ''))
    require(result_path.is_file() and sha(result_path) == processing.get('result_sha256'),
            'Saved result missing or changed')
    result = read(result_path)
    require(result.get('case_id') == case and result.get('accepted') is False and
            result.get('video_frame_map_reference') == 'video_frames.jsonl' and
            len(result.get('target_checks', [])) == 1 and
            result['target_checks'][0].get('matched') is True,
            'Saved parking measurement or acceptance boundary differs')
    require(processing.get('final_video_checks', {}).get('passed') is True and
            processing['final_video_checks'].get('frames') == 600,
            'Full composed video decode missing')
    original_complete = False
    if not diagnostic:
        require(inventory.get('source_kind') == 'original_native',
                'Original Native parking source required')
        require(review_path is not None, 'Original physical review required')
        review = read(review_path)
        require(review.get('case_id') == case and
                review.get('attempt_source_hashes') == {
                    name: source_hashes[name] for name in SOURCES},
                'Original physical review binds another source')
        require(all(review.get(flag) is True for flag in REVIEW_FLAGS),
                'City context, actual pixels, or physical completion review incomplete')
        original_complete = True
    return {'format': 'c150129-delivery-source-audit', 'case_id': case,
            'passed': True, 'diagnostic_fixture': diagnostic,
            'original_source_frame_count': 600, 'camera_decodes': cameras,
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
    result = audit(args.case, args.attempt, args.processing, args.diagnostic, args.review)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))
