"""Bind a possible fire-lane stop event to retained motion sources.

Near-zero speed is an engineering observation. It does not decide whether the
legal act was stopping, standing or parking, or whether an exception applies.
"""
import argparse
import json
from pathlib import Path

from fire_lane_survey import require
from source_measurement import analyze, sha


def _episodes(samples, predicate):
    runs, start = [], None
    for index, sample in enumerate(samples):
        if predicate(sample):
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index - 1))
            start = None
    if start is not None:
        runs.append((start, len(samples) - 1))
    return [{'first_frame': samples[first]['carla_frame'],
             'last_frame': samples[last]['carla_frame'],
             'first_time_s': samples[first]['time_s'],
             'last_time_s': samples[last]['time_s'],
             'sample_count': last - first + 1,
             'sampled_duration_s': (last - first + 1) / 20}
            for first, last in runs]


def build(attempt, case, *, diagnostic=False):
    attempt = Path(attempt)
    provenance_path = attempt / 'acquisition-provenance.json'
    require(provenance_path.is_file(), 'Missing acquisition provenance')
    provenance = json.loads(provenance_path.read_text())
    expected = ('synthetic_fixture', True) if diagnostic else ('native', False)
    require((provenance.get('provenance_kind'),
             provenance.get('diagnostic_fixture')) == expected,
            'Acquisition provenance differs from requested mode')
    measured = analyze(attempt, case, diagnostic=diagnostic)
    require(measured['frames'] >= 600 and
            measured['physical_or_legal_completion_claimed'] is False,
            'Full source capture or claim guard missing')
    samples = measured['samples']
    require(all(abs(sample['time_s'] - index / 20) < 1e-4
                for index, sample in enumerate(samples)),
            'Motion source is not a continuous 20 Hz capture')
    survey = json.loads((attempt / 'native-survey-readback.json').read_text())
    near_zero = _episodes(samples, lambda row: row['speed_mps'] <= 0.05)
    in_zone = _episodes(samples, lambda row:
                        row['speed_mps'] <= 0.05 and
                        row['body_zone_overlap_m2'] > 0)
    outside_zone = _episodes(samples, lambda row:
                             row['speed_mps'] <= 0.05 and
                             row['body_disjoint_from_authored_zone'])
    return {
        'format': 'c201084-source-bound-motion-event-v1',
        'case': case, 'source_kind': measured['source_kind'],
        'diagnostic_fixture': diagnostic, 'frames': measured['frames'],
        'capture_hz': 20, 'ego_actor_id': measured['ego_actor_id'],
        'source_sha256': {
            'acquisition-provenance.json': sha(provenance_path),
            'native-actors.jsonl': measured['actor_source_sha256'],
            'video_frames.jsonl': measured['frame_map_sha256'],
            'native-survey-readback.json': measured['survey_readback_sha256'],
            **{video['path']: video['sha256'] for video in
               measured['source_camera_videos'].values()}},
        'near_zero_tolerance_mps': 0.05,
        'near_zero_episodes': near_zero,
        'near_zero_authored_zone_overlap_episodes': in_zone,
        'near_zero_outside_authored_zone_episodes': outside_zone,
        'authored_property_context': survey['fixed_context']['property_context'],
        'unresolved_source_review': [
            'original sign face and City Fire Code lane designation',
            'original public or private property status',
            'driver attendance and whether the act is stopping, standing or parking',
            'applicable law and any traffic, police or device direction',
            'statutory necessity and legal compliance'],
        'original_posting_or_designation_verified': False,
        'property_status_verified': False,
        'driver_attendance_verified': False,
        'legal_act_classification': None,
        'statutory_necessity_verified': False,
        'physical_or_legal_completion_claimed': False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--case', required=True, choices=('reference', 'contrast'))
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    require(not args.output.exists(), 'Event evidence output already exists')
    result = build(args.attempt, args.case, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
