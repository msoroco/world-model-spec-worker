"""Source-bound C111088 attempt finalization; original files are never rewritten."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from engineering import parameters
from measure import joined_samples, measure_arrow_and_yield


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path: Path) -> str:
    if not path.is_file():
        raise ValueError('Missing original source: ' + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decoded_frames(path: Path) -> int:
    completed = subprocess.run([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=nb_read_frames',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
    if completed.returncode or not completed.stdout.strip().isdigit():
        raise ValueError('Original source video does not decode: ' + path.name)
    return int(completed.stdout.strip())


def verified_arrow_frames(attempt: Path, count: int) -> tuple[set[int], dict]:
    """Require separate pixel review bound to both signal-bearing source videos."""
    path = attempt / 'aspect-review.json'
    if not path.is_file():
        raise ValueError('Independent source-pixel aspect review absent')
    review = json.loads(path.read_text())
    if review.get('review_kind') != 'original_source_pixel_aspect' or \
       review.get('sole_green_straight_arrow') is not True or \
       review.get('governs_ego') is not True or \
       not review.get('reviewer') or not review.get('method'):
        raise ValueError('Original pixel aspect/governing review incomplete')
    expected = {name + '.mkv': sha(attempt / (name + '.mkv'))
                for name in ('overview', 'reference_corner')}
    if review.get('source_video_sha256') != expected:
        raise ValueError('Pixel aspect review source hashes differ')
    start = review.get('first_video_frame')
    end = review.get('last_video_frame')
    if type(start) is not int or type(end) is not int or start < 0 or end >= count or end < start:
        raise ValueError('Pixel aspect review frame interval invalid')
    if end - start < 20:
        raise ValueError('Pixel aspect review interval too short for entry event')
    return set(range(start, end + 1)), {'review_sha256': sha(path),
                                       'source_video_sha256': expected,
                                       'first_video_frame': start,
                                       'last_video_frame': end}


def finalize(attempt: Path, report_path: Path) -> dict:
    attempt = attempt.resolve()
    report_path = report_path.resolve()
    if (attempt / 'result.json').exists() or report_path.exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    if config != parameters(config['case_id'], config['candidate_id']):
        raise ValueError('Exact construction config differs')
    count = config['rate_hz'] * config['duration_s']
    samples, joins = joined_samples(attempt, rate_hz=config['rate_hz'],
                                    duration_s=config['duration_s'])
    video_hashes = {name + '.mkv': sha(attempt / (name + '.mkv')) for name in CAMERAS}
    video_counts = {name: decoded_frames(attempt / name) for name in video_hashes}
    if any(value != count for value in video_counts.values()):
        raise ValueError('Original source camera frame count differs')
    verified, pixel_review = verified_arrow_frames(attempt, count)
    measured = measure_arrow_and_yield(samples, verified_arrow_frames=verified)
    requested = config['lawful_conflict_participant_present']
    present = measured['other_vehicle_present_under_verified_arrow']
    prior_entry = measured['prior_green_entry_within_verified_arrow']
    target_matched = present == requested and (not requested or prior_entry)
    straight = measured['straight_heading_no_turn_observed']
    body_exit = min(vertex[1] for vertex in samples[-1]['native_body_xy_m']) > 7
    result = {
        'case_id': config['case_id'],
        'measured_values': {'straight_arrow_and_yield': measured,
                            'original_joins': joins, 'pixel_review': pixel_review,
                            'video_sha256': video_hashes, 'video_decoded_frames': video_counts},
        'target_checks': [
            {'target': 'prior-entered other vehicle occupies intersection under sole arrow',
             'requested': requested, 'measured': present and prior_entry,
             'method': 'saved original Native actor footprint, west signal history and source pixels',
             'tolerance': 0, 'matched': target_matched,
             'physical_cause_confirmed': False,
             'cause_evidence': ['native_samples.jsonl', 'aspect-review.json', 'road_geometry.json']},
            {'target': 'ego proceeds straight and yields until conflict clears',
             'requested': True, 'measured': straight and measured['yielded_before_entry'],
             'method': 'saved original Native heading, full body and other-vehicle occupancy',
             'tolerance': 0, 'matched': straight and measured['yielded_before_entry'],
             'physical_cause_confirmed': False,
             'cause_evidence': ['native_samples.jsonl', 'body_history.jsonl']},
        ],
        'setup_confirmed': True,
        'behavior_attempted': True,
        'maneuver_completed': body_exit,
        'termination_reason': 'full 42-second original Native capture retained',
        'physical_failure_flags': [] if target_matched and straight and body_exit and
            measured['yielded_before_entry'] else ['controlled_target_or_motion_unconfirmed'],
        'trace_reference': 'trace.jsonl',
        'video_references': list(video_hashes),
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': {'channels': []},
        'recording_evidence': [],
        'realized_observables': {
            'first_front_stop_line_crossing_frame': {
                'value': measured['first_front_stop_line_crossing_frame'], 'unit': 'frame',
                'method': 'saved original Native full-body line crossing',
                'time_window': 'full original 42-second attempt',
                'statistic': 'first', 'reference': 'native_samples.jsonl'}},
        'provenance_kind': 'native', 'accepted': False, 'legal_verdict_claimed': False,
    }
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111088-saved-source-analysis-v1',
              'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
              'measurements': measured, 'original_joins': joins,
              'source_camera_sha256': video_hashes, 'source_camera_frames': video_counts,
              'pixel_review': pixel_review,
              'scope': 'saved original Native and source video; no legal verdict or acceptance'}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (attempt / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.report), allow_nan=False))


if __name__ == '__main__':
    main()
