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
        raise ValueError('Missing required source: ' + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_arrow_aspect(measured: dict) -> dict:
    return {'active_frames': measured['sole_arrow_pixel_verified_frames'],
            'pixel_review_required': True}


def measure_straight_motion(measured: dict) -> bool:
    return measured['straight_heading_no_turn_observed']


def measure_yield_timing(measured: dict) -> dict:
    return {'other_vehicle_present': measured['other_vehicle_present_under_verified_arrow'],
            'prior_green_entry_observed': measured['prior_green_entry_within_verified_arrow'],
            'ego_first_crossing_frame': measured['first_front_stop_line_crossing_frame'],
            'other_last_occupancy_frame': measured['last_other_vehicle_occupancy_under_verified_arrow_frame'],
            'yielded_before_entry': measured['yielded_before_entry'],
            'legal_right_of_way_determined': False}


def measure_other_vehicle_conflict(measured: dict) -> bool:
    return measured['other_vehicle_present_under_verified_arrow']


MEASUREMENT_INPUTS = {
    'arrow_aspect': ('aspect-review.json', 'overview.mkv', 'reference_corner.mkv'),
    'straight_motion': ('native_samples.jsonl', 'body_history.jsonl'),
    'yield_timing': ('native_samples.jsonl', 'road_geometry.json', 'aspect-review.json'),
    'other_vehicle_conflict': ('native_samples.jsonl', 'road_geometry.json'),
}


def measurement_rows(attempt: Path, measured: dict) -> dict:
    methods = {
        'arrow_aspect': measure_arrow_aspect,
        'straight_motion': measure_straight_motion,
        'yield_timing': measure_yield_timing,
        'other_vehicle_conflict': measure_other_vehicle_conflict,
    }
    return {key: {'value': method(measured), 'method': method.__name__,
                  'sources': {name: sha(attempt / name) for name in MEASUREMENT_INPUTS[key]}}
            for key, method in methods.items()}


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
    capture_manifest = attempt / 'capture' / 'manifest.json'
    if capture_manifest.is_file():
        capture = json.loads(capture_manifest.read_text())
        if capture.get('synthetic_diagnostic') is True:
            path = attempt / 'aspect-review.json'
            if not path.is_file():
                raise ValueError('Missing required source: aspect-review.json')
            review = json.loads(path.read_text())
            if review.get('review_kind') != 'synthetic_fixture_aspect' or \
               review.get('original_pixel_reviewed') is not False or \
               review.get('diagnostic_only') is not True:
                raise ValueError('Synthetic aspect declaration incomplete')
            start, end = review.get('first_video_frame'), review.get('last_video_frame')
            if type(start) is not int or type(end) is not int or start < 0 or end >= count or end < start:
                raise ValueError('Synthetic aspect frame interval invalid')
            return set(range(start, end + 1)), {
                'review_sha256': sha(path), 'kind': 'synthetic_fixture_aspect',
                'original_pixel_reviewed': False, 'diagnostic_only': True,
                'first_video_frame': start, 'last_video_frame': end}
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
                                       'kind': 'original_source_pixel_aspect',
                                       'source_video_sha256': expected,
                                       'first_video_frame': start,
                                       'last_video_frame': end}


def derive_channels(attempt: Path, description: dict, samples: list[dict],
                    mapping: list[dict], geometry: dict) -> list[dict]:
    """Create mandatory channels from retained raw sources, never fixture channels."""
    channel_dir = attempt / 'channels'
    channel_dir.mkdir(exist_ok=True)
    evidence = []
    if len(samples) != len(mapping):
        raise ValueError('Saved source/channel frame count differs')
    for channel in description['channels']:
        name = channel['name']
        path = channel_dir / (name + '.jsonl')
        with path.open('x') as stream:
            for sample, frame_map in zip(samples, mapping):
                signal = sample['governing_signal']
                other = sample['other_vehicle']
                source_values = {
                    'dev.traffic_signal': signal,
                    'dev.governs': {'native_actor_id': signal['native_actor_id'],
                                    'facing_ego_native_survey': signal['facing_ego_native_survey']},
                    'drv.turning': {'heading_deg': sample['native_yaw_deg']},
                    'kin.heading': {'heading_deg': sample['native_yaw_deg']},
                    'drv.entering_intersection': {
                        'ego_body_xy_m': sample['native_body_xy_m'],
                        'intersection_bounds_xy_m': geometry['intersection_bounds_xy_m']},
                    'st.crosswalk': {'crosswalk_points_xy_m': geometry['adjacent_crosswalk_xy_m']},
                    'drv.in_intersection': other,
                    'drv.yields_to': {'other_actor_id': other['native_actor_id'],
                                      'controller_request': sample['controller_request'],
                                      'other_occupied': other['within_intersection_or_adjacent_crosswalk']},
                    'st.intersection': {'intersection_bounds_xy_m': geometry['intersection_bounds_xy_m']},
                    'kin.position': {'native_center_xy_m': sample['native_center_xy_m']},
                    'native_body_pose_control': sample,
                    'camera_frame_join': frame_map,
                }
                if name not in source_values:
                    raise ValueError('Unsupported source-derived channel: ' + name)
                stream.write(json.dumps({'time_s': sample['time_s'],
                                         'value': source_values[name]}, allow_nan=False) + '\n')
        evidence.append({'name': name, 'unit': channel['unit'],
                         'reference': 'channels/' + name + '.jsonl'})
    return evidence


def finalize(attempt: Path, report_path: Path) -> dict:
    attempt = attempt.resolve()
    report_path = report_path.resolve()
    if (attempt / 'result.json').exists() or report_path.exists():
        raise ValueError('Retain prior finalization; use a fresh attempt')
    config = json.loads((attempt / 'config.json').read_text())
    sha(attempt / 'native_samples.jsonl')
    expected = parameters(config['case_id'], config['candidate_id'])
    if any(config.get(key) != value for key, value in expected.items()):
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
    description = config['recording_description']
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    geometry = json.loads((attempt / 'road_geometry.json').read_text())
    recording_evidence = derive_channels(attempt, description, samples, mapping, geometry)
    context_path = attempt / 'surveyed-arrow-context.json'
    context_value = {'surveyed_arrow_intersection': {
            'intersection_bounds_xy_m': geometry['intersection_bounds_xy_m'],
            'adjacent_crosswalk_xy_m': geometry['adjacent_crosswalk_xy_m'],
            'native_map_sha256': geometry['native_map_sha256'],
            'authored_aspect': geometry['authored_aspect'],
            'original_pixel_reviewed': pixel_review.get('kind') == 'original_source_pixel_aspect',
        }}
    if context_path.exists():
        if json.loads(context_path.read_text()) != context_value:
            raise ValueError('Existing derived context differs from retained sources')
    else:
        with context_path.open('x') as stream:
            json.dump(context_value, stream, allow_nan=False)
            stream.write('\n')
    recording_evidence.append({'name': description['context_inputs'][0]['name'],
                               'unit': description['context_inputs'][0]['unit'],
                               'reference': 'surveyed-arrow-context.json'})
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
        'recording_description': description,
        'recording_evidence': recording_evidence,
        'realized_observables': {
            'first_front_stop_line_crossing_frame': {
                'value': measured['first_front_stop_line_crossing_frame'], 'unit': 'frame',
                'method': 'saved original Native full-body line crossing',
                'time_window': 'full original 42-second attempt',
                'statistic': 'first', 'reference': 'native_samples.jsonl'}},
        'provenance_kind': 'native', 'accepted': False, 'legal_verdict_claimed': False,
    }
    diagnostic = pixel_review.get('diagnostic_only') is True
    if diagnostic:
        result['provenance_kind'] = 'synthetic_native_sample'
        result['termination_reason'] = '42-second synthetic CPU diagnostic; no original Native capture'
        for check in result['target_checks']:
            check['method'] = 'synthetic Native sample and declared synthetic aspect; diagnostic only'
        result['realized_observables']['first_front_stop_line_crossing_frame']['method'] = \
            'synthetic Native sample body crossing; diagnostic only'
    from worker_exchange.native_output import validate_result
    validate_result(result)
    report = {'format': 'c111088-saved-source-analysis-v1',
              'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
              'measurements': measurement_rows(attempt, measured),
              'measurement_summary': measured, 'original_joins': joins,
              'source_camera_sha256': video_hashes, 'source_camera_frames': video_counts,
              'pixel_review': pixel_review,
              'scope': ('synthetic CPU diagnostic only; no original pixel, Native, physical or legal claim'
                        if diagnostic else 'saved original Native and source video; no legal verdict or acceptance')}
    report_path.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (attempt / 'result.json').open('x') as stream:
        json.dump(result, stream, indent=2, allow_nan=False)
        stream.write('\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', '--report', dest='report', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.report), allow_nan=False))


if __name__ == '__main__':
    main()
