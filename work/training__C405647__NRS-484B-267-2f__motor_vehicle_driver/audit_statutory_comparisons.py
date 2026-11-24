"""Compare fixed approach sources against hand and officer exception variants."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from measure_hand_signal_approach import measure as measure_hand
from measure_officer_approach import measure as measure_officer


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit(suffix, variant=None):
    if suffix not in ('visible_hand_signal', 'officer_direction'):
        raise ValueError('Select one statutory variant')
    base_suffix = 'controlled_1' if suffix == 'visible_hand_signal' else 'controlled_2'
    baseline = HERE / 'current-fixture' / base_suffix
    variant = Path(variant) if variant else HERE / ('draft-hand-signal/source' if suffix == 'visible_hand_signal'
                                                   else 'draft-officer/source')
    measurement = (measure_hand if suffix == 'visible_hand_signal' else measure_officer)(variant)
    baseline_frames = rows(baseline / 'video_frames.jsonl')
    variant_frames = rows(variant / 'video_frames.jsonl')
    baseline_poses = rows(baseline / 'vehicle_poses.jsonl')
    variant_poses = rows(variant / 'vehicle_poses.jsonl')
    if len(baseline_frames) != 600 or len(variant_frames) != 600:
        raise ValueError('Full fixed-frame comparison required')
    for index, (before_frame, after_frame, before_pose, after_pose) in enumerate(
            zip(baseline_frames, variant_frames, baseline_poses, variant_poses)):
        if before_frame != after_frame or before_pose != after_pose:
            raise ValueError('Fixed frame, vehicle path or flashing-light program differs at ' + str(index))
    changed = measurement['hand_signal_indicator'] if suffix == 'visible_hand_signal' else measurement['officer_direction_indicator']
    return {'format': 'c405647-2f-statutory-comparison-v1',
            'case_id': HERE.name + '__' + suffix,
            'baseline_case_id': HERE.name + '__' + base_suffix,
            'fixed_vehicle_frames': 600,
            'deliberate_difference': 'source-driver hand signal' if suffix == 'visible_hand_signal'
                                     else 'officer direction',
            'indicator_start_frame': changed['signal_start_frame'] if suffix == 'visible_hand_signal'
                                     else changed['direction_start_frame'],
            'indicator_end_frame': changed['signal_end_frame'] if suffix == 'visible_hand_signal'
                                   else changed['direction_end_frame'],
            'baseline_source_sha256': {name: sha(baseline / name)
                                       for name in ('video_frames.jsonl', 'vehicle_poses.jsonl')},
            'variant_source_sha256': measurement['source_sha256'],
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=('visible_hand_signal', 'officer_direction'), required=True)
    parser.add_argument('--variant', type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.variant), sort_keys=True))
