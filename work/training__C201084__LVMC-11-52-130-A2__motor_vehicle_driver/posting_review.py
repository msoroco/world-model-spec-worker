"""Bind a human sign/posting review to retained decoded video frames.

This records what a reviewer claimed to see. It never decides whether the
posting meets the City Fire Code or whether the law applies to the event.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from fire_lane_survey import CAMERAS, require
from source_measurement import camera_sources, read_lines, sha


HERE = Path(__file__).resolve().parent


def decoded_frame_sha(video, index):
    command = ['ffmpeg', '-v', 'error', '-i', str(video), '-vf',
               'select=eq(n\\,' + str(index) + ')', '-frames:v', '1',
               '-f', 'image2pipe', '-vcodec', 'png', 'pipe:1']
    process = subprocess.run(command, capture_output=True)
    require(process.returncode == 0 and process.stdout,
            'Could not decode retained posting frame')
    return hashlib.sha256(process.stdout).hexdigest()


def _source(attempt, reference):
    require(isinstance(reference, dict) and
            isinstance(reference.get('path'), str) and
            isinstance(reference.get('sha256'), str),
            'Designation document reference missing')
    relative = Path(reference['path'])
    require(not relative.is_absolute() and '..' not in relative.parts and
            relative.parts and relative.parts[0] not in ('channels', 'analysis'),
            'Designation document must be a retained attempt file')
    path = attempt / relative
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size > 0 and sha(path) == reference['sha256'],
            'Designation document source differs')
    return relative.as_posix()


def build(attempt, event_path, review_path=None):
    attempt, event_path = Path(attempt), Path(event_path)
    event = json.loads(event_path.read_text())
    require(event.get('format') == 'c201084-source-bound-motion-event-v1' and
            event.get('frames') == 600 and event.get('capture_hz') == 20 and
            event.get('physical_or_legal_completion_claimed') is False,
            'Posting review event differs')
    for relative, digest in event['source_sha256'].items():
        require(sha(attempt / relative) == digest,
                'Posting review event source differs: ' + relative)
    frames = read_lines(attempt / 'video_frames.jsonl')
    require(len(frames) == event['frames'], 'Posting frame map differs')
    cameras = camera_sources(attempt, event['frames'])
    require(set(cameras) == set(CAMERAS), 'Posting four-camera source incomplete')
    bound = None
    if review_path is not None:
        review_path = Path(review_path)
        review = json.loads(review_path.read_text())
        require(isinstance(review, dict) and
                review.get('format') == 'c201084-posting-source-review-v1' and
                review.get('case_id') == HERE.name + '__' + event['case'] and
                isinstance(review.get('reviewer'), str) and
                review['reviewer'].strip() and
                review.get('review_kind') == (
                    'synthetic_annotation' if event['diagnostic_fixture'] else
                    'original_source_review'),
                'Posting review identity or provenance differs')
        document = review.get('designation_document')
        require(isinstance(document, dict) and
                isinstance(document.get('description'), str) and
                document['description'].strip(),
                'Designation document description missing')
        document_path = _source(attempt, document.get('source'))
        observations = review.get('sign_observations')
        require(isinstance(observations, list) and observations,
                'Posting review has no sign observations')
        bound_observations = []
        for observation in observations:
            require(isinstance(observation, dict) and
                    observation.get('camera') in CAMERAS and
                    type(observation.get('video_frame')) is int and
                    0 <= observation['video_frame'] < len(frames) and
                    observation.get('video_sha256') ==
                        cameras[observation['camera']]['sha256'] and
                    observation.get('carla_frame') ==
                        frames[observation['video_frame']]['carla_frame'] and
                    isinstance(observation.get('review_note'), str) and
                    observation['review_note'].strip(),
                    'Posting observation is not bound to a retained frame')
            roi = observation.get('roi_xywh')
            camera = cameras[observation['camera']]
            require(isinstance(roi, list) and len(roi) == 4 and
                    all(type(x) is int for x in roi) and
                    roi[0] >= 0 and roi[1] >= 0 and
                    roi[2] > 0 and roi[3] > 0 and
                    roi[0] + roi[2] <= camera['width'] and
                    roi[1] + roi[3] <= camera['height'],
                    'Posting observation ROI is outside the decoded image')
            frame_sha = decoded_frame_sha(
                attempt / camera['path'], observation['video_frame'])
            require(observation.get('decoded_frame_sha256') == frame_sha,
                    'Posting decoded frame differs')
            bound_observations.append({
                'camera': observation['camera'],
                'video_frame': observation['video_frame'],
                'carla_frame': observation['carla_frame'],
                'decoded_frame_sha256': frame_sha,
                'roi_xywh': roi,
                'review_note': observation['review_note']})
        bound = {'review_kind': review['review_kind'],
                 'reviewer': review['reviewer'],
                 'designation_document_path': document_path,
                 'designation_document_sha256': document['source']['sha256'],
                 'sign_observations': bound_observations,
                 'review_sha256': sha(review_path)}
    return {'format': 'c201084-retained-posting-review-binding-v1',
            'case': event['case'],
            'diagnostic_fixture': event['diagnostic_fixture'],
            'event_evidence_sha256': sha(event_path),
            'camera_source_sha256': {name: camera['sha256'] for
                                     name, camera in cameras.items()},
            'posting_review': bound,
            'original_posting_review_bound': bool(
                bound and not event['diagnostic_fixture']),
            'sign_text_verified': False,
            'fire_code_designation_verified': False,
            'legal_applicability_verified': False,
            'physical_or_legal_completion_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--event', required=True, type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior posting binding')
    args.output.write_text(json.dumps(
        build(args.attempt, args.event, args.review), indent=2,
        sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
