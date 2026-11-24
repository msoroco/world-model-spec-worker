"""Fail-closed original Native pixel and signal-governance review contract."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(attempt, review):
    attempt, review = Path(attempt), Path(review)
    config = read(attempt / 'config.json')
    report_path = attempt / 'native-capture-report.json'
    if not report_path.is_file():
        raise ValueError('Original Native capture report required')
    report = read(report_path)
    if report.get('case_id') != config['case_id'] or report.get('frames') != 600 or \
            report.get('error') is not None or not report.get('restoration'):
        raise ValueError('Complete restored Native capture required')
    review_data = read(review)
    if review_data.get('case_id') != config['case_id'] or \
            review_data.get('native_capture_report_sha256') != sha(report_path) or \
            review_data.get('provenance') != 'original_native' or \
            not review_data.get('reviewer'):
        raise ValueError('Independent original Native review binding required')
    if not review_data.get('governing_direction_physically_verified') or \
            not review_data.get('marked_crosswalk_physically_verified') or \
            not review_data.get('circular_green_alone_pixels_verified') or \
            not review_data.get('pedestrian_indication_pixels_verified'):
        raise ValueError('Original pixels, crosswalk and governing direction unverified')
    frames = review_data.get('reviewed_frames')
    if not isinstance(frames, list) or not frames or any(
            not isinstance(frame, int) or frame < 0 or frame >= 600 for frame in frames):
        raise ValueError('Original review frame identities missing')
    video_hashes = review_data.get('source_video_sha256')
    if not isinstance(video_hashes, dict) or set(video_hashes) != set(CAMERAS):
        raise ValueError('Four original source videos required')
    decoded = {}
    for camera in CAMERAS:
        video = attempt / (camera + '.mkv')
        if not video.is_file() or sha(video) != video_hashes[camera]:
            raise ValueError('Original camera video hash differs: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
            '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_frames',
            '-of', 'default=nokey=1:noprint_wrappers=1', str(video)],
            capture_output=True, text=True, check=True)
        if probe.stdout.strip() != '600':
            raise ValueError('Complete original camera decode required: ' + camera)
        decoded[camera] = 600
    return {'format': 'c111331-physical-review-v1', 'case_id': config['case_id'],
            'native_capture_report_sha256': sha(report_path),
            'source_video_sha256': video_hashes, 'decoded_frames': decoded,
            'reviewed_frames': frames, 'physical_completion_reviewed': True,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt, args.review), indent=2) + '\n')
