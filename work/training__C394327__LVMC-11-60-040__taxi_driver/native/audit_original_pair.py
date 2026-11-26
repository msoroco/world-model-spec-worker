"""Independent original-source comparison for the taxi loading pair.

This is a prospective local audit. A generated request is never an original
attempt, and this audit never returns a legal compliance verdict.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

from finalize_original import finalize

PREFIX = 'training__C394327__LVMC-11-60-040__taxi_driver__'
CASES = (PREFIX + 'probe_a', PREFIX + 'probe_b')
FRAMES = 600


def require(value, message):
    if not value:
        raise ValueError(message)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compare(left_measure, right_measure, left_native, right_native,
            left_activity, right_activity):
    require(left_measure.get('requested_activity') == 'passenger_loading' and
            right_measure.get('requested_activity') == 'merchandise_loading',
            'Original passenger/merchandise activity contrast missing')
    require(left_measure.get('occupant_count_max', 0) >
            left_measure.get('occupant_count_min', 0) and
            right_measure.get('occupant_count_max') ==
            right_measure.get('occupant_count_min'),
            'Original passenger exchange or merchandise contrast missing')
    require(len(left_native) == len(right_native) == len(left_activity) ==
            len(right_activity) == FRAMES,
            'Original comparison requires two complete 600-frame sources')
    for index, (ln, rn, la, ra) in enumerate(zip(
            left_native, right_native, left_activity, right_activity)):
        require(ln.get('video_frame') == rn.get('video_frame') ==
                la.get('video_frame') == ra.get('video_frame') == index and
                ln.get('time_s') == rn.get('time_s') ==
                la.get('time_s') == ra.get('time_s') == (index + 1) / 20,
                'Original comparison frame/time join differs')
        require(la.get('observed_taxi_identity') is True and
                ra.get('observed_taxi_identity') is True and
                la.get('observed_stand_location') ==
                ra.get('observed_stand_location') == 'outside_designated_stand',
                'Original taxi or outside-stand condition differs')
        require(ln.get('taxi_blueprint_id') and
                ln.get('taxi_blueprint_id') == rn.get('taxi_blueprint_id'),
                'Original taxi actor type differs')
        for key in ('taxi_xyz_m', 'taxi_velocity_xyz_mps'):
            lv, rv = ln.get(key), rn.get(key)
            require(isinstance(lv, list) and isinstance(rv, list) and
                    len(lv) == len(rv) == 3 and all(
                        type(v) in (int, float) and math.isfinite(v)
                        for v in lv + rv) and all(
                        abs(a - b) <= (0.5 if key == 'taxi_xyz_m' else 0.1)
                        for a, b in zip(lv, rv)),
                    'Original taxi pose or stop differs: ' + key)
        require(la.get('observed_door_open') == ra.get('observed_door_open') and
                la.get('observed_speed_mps') == ra.get('observed_speed_mps'),
                'Original door or stopped-speed control differs')
    return {'case_ids': list(CASES), 'frames_per_case': FRAMES,
            'fixed_taxi_stand_pose_speed_door_timing': True,
            'deliberate_differences': ['loading_subject_and_occupant_transition'],
            'legal_verdict': None}


def audit(left_attempt, right_attempt, output):
    attempts = [Path(left_attempt).resolve(), Path(right_attempt).resolve()]
    for case, attempt in zip(CASES, attempts):
        require(attempt.is_dir(), 'Original attempt directory missing')
        review_manifest = json.loads((attempt / 'review-manifest.json').read_text())
        require(review_manifest.get('case_id') == case,
                'Original review manifest binds another exact case')
    require(sha(attempts[0] / 'road.xodr') == sha(attempts[1] / 'road.xodr'),
            'Original road and stand geometry differs')
    measurements = [finalize(attempt, attempt / 'review-manifest.json')
                    for attempt in attempts]
    require(all(measurement.get('original_native_observed') is True and
                measurement.get('legal_verdict') is None
                for measurement in measurements),
            'Synthetic or unobserved source cannot establish original comparison')
    native = [read_rows(attempt / 'native-rows.jsonl') for attempt in attempts]
    activity = [read_rows(attempt / 'observed-activity.jsonl') for attempt in attempts]
    result = compare(measurements[0], measurements[1], native[0], native[1],
                     activity[0], activity[1])
    result.update({'format': 'worker-original-taxi-comparison',
                   'passed': True,
                   'review_manifest_sha256': [sha(attempt / 'review-manifest.json')
                                             for attempt in attempts],
                   'native_rows_sha256': [sha(attempt / 'native-rows.jsonl')
                                          for attempt in attempts],
                   'observed_activity_sha256': [sha(attempt / 'observed-activity.jsonl')
                                                for attempt in attempts]})
    Path(output).write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left-attempt', required=True)
    parser.add_argument('--right-attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    audit(args.left_attempt, args.right_attempt, args.output)
