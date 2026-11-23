"""Bind property and attendance review claims to retained sources.

This checks source identity and temporal coverage, not the truth of a reviewer's
interpretation or the legal validity of a Fire Code designation.
"""
import argparse
import json
from pathlib import Path

from fire_lane_survey import CAMERAS, require
from source_measurement import camera_sources, read_lines, sha


HERE = Path(__file__).resolve().parent


def _source(attempt, claim):
    require(isinstance(claim, dict) and
            isinstance(claim.get('path'), str) and
            isinstance(claim.get('sha256'), str),
            'Property source reference missing')
    relative = Path(claim['path'])
    require(not relative.is_absolute() and '..' not in relative.parts and
            relative.parts and relative.parts[0] not in ('channels', 'analysis'),
            'Property source must be a retained attempt file')
    path = attempt / relative
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size > 0 and sha(path) == claim['sha256'],
            'Property source file or hash differs')
    return relative.as_posix()


def _review(attempt, event, frames, cameras, review):
    case_id = HERE.name + '__' + event['case']
    require(isinstance(review, dict) and
            review.get('format') == 'c201084-context-source-review-v1' and
            review.get('case_id') == case_id and
            isinstance(review.get('reviewer'), str) and
            review['reviewer'].strip() and
            review.get('review_kind') == (
                'synthetic_annotation' if event['diagnostic_fixture'] else
                'original_source_review'),
            'Context review identity or provenance differs')
    property_claim = review.get('property')
    require(isinstance(property_claim, dict) and
            property_claim.get('status') in ('public', 'private') and
            isinstance(property_claim.get('basis'), str) and
            property_claim['basis'].strip(),
            'Property status claim is incomplete')
    property_source = _source(attempt, property_claim.get('source'))
    attendance = review.get('attendance')
    require(isinstance(attendance, dict) and
            attendance.get('state') in ('attended', 'unattended') and
            isinstance(attendance.get('basis'), str) and
            attendance['basis'].strip(),
            'Attendance source claim is incomplete')
    intervals = attendance.get('reviewed_intervals')
    require(isinstance(intervals, list) and intervals,
            'Attendance has no continuous reviewed intervals')
    covered = set()
    for interval in intervals:
        require(isinstance(interval, dict) and
                interval.get('camera') in CAMERAS and
                interval.get('video_sha256') ==
                    cameras[interval['camera']]['sha256'] and
                type(interval.get('first_video_frame')) is int and
                type(interval.get('last_video_frame')) is int,
                'Attendance interval lacks bound video source')
        first, last = interval['first_video_frame'], interval['last_video_frame']
        require(0 <= first <= last < len(frames) and
                interval.get('first_carla_frame') == frames[first]['carla_frame'] and
                interval.get('last_carla_frame') == frames[last]['carla_frame'] and
                interval.get('continuous_review') is True,
                'Attendance interval is not bound to a continuous frame span')
        covered.update(range(first, last + 1))
    frame_indices = {row['carla_frame']: index for index, row in enumerate(frames)}
    for episode in event['near_zero_episodes']:
        first = frame_indices.get(episode['first_frame'])
        last = frame_indices.get(episode['last_frame'])
        require(first is not None and last is not None and
                set(range(first, last + 1)) <= covered,
                'Attendance review does not cover the full near-zero episode')
    return {'review_kind': review['review_kind'],
            'reviewer': review['reviewer'],
            'property_status_claim': property_claim['status'],
            'property_source': property_source,
            'attendance_state_claim': attendance['state'],
            'continuous_attendance_review_covers_near_zero_events': True,
            'review_sha256': None}


def build(attempt, event_path, review_path=None):
    attempt, event_path = Path(attempt), Path(event_path)
    event = json.loads(event_path.read_text())
    require(event.get('format') == 'c201084-source-bound-motion-event-v1' and
            event.get('frames') >= 600 and event.get('capture_hz') == 20 and
            event.get('physical_or_legal_completion_claimed') is False,
            'Motion event evidence differs')
    for relative, digest in event['source_sha256'].items():
        require(sha(attempt / relative) == digest,
                'Motion event source binding differs: ' + relative)
    frames = read_lines(attempt / 'video_frames.jsonl')
    require(len(frames) == event['frames'], 'Context frame count differs')
    cameras = camera_sources(attempt, event['frames'])
    require(set(cameras) == set(CAMERAS), 'Four-camera source review incomplete')
    review = None
    if review_path is not None:
        review_path = Path(review_path)
        review = _review(attempt, event, frames, cameras,
                         json.loads(review_path.read_text()))
        review['review_sha256'] = sha(review_path)
    return {'format': 'c201084-retained-context-review-binding-v1',
            'case': event['case'],
            'diagnostic_fixture': event['diagnostic_fixture'],
            'event_evidence_sha256': sha(event_path),
            'camera_source_sha256': {name: row['sha256'] for name, row in
                                     cameras.items()},
            'property_and_attendance_review': review,
            'original_context_review_bound': bool(
                review and not event['diagnostic_fixture']),
            'property_legally_verified': False,
            'posting_or_fire_code_designation_verified': False,
            'statutory_necessity_verified': False,
            'physical_or_legal_completion_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--event', required=True, type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Retain prior context review binding')
    result = build(args.attempt, args.event, args.review)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
