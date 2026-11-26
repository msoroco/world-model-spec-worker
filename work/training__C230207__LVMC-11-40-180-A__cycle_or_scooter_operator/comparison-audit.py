"""Independent source-bound comparison pre-audit for the two exact cases."""
import argparse
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from measure import measure

FIXED = ('street_name', 'west_boundary', 'east_boundary', 'sidewalk_xy_m',
         'sign_text', 'sign_id', 'rider_class', 'blueprint_id')


def audit(walk_sources, ride_sources):
    contexts = [json.loads(Path(sources[1]).read_text()) for sources in
                (walk_sources, ride_sources)]
    walk_context, ride_context = contexts
    if any(walk_context.get(key) != ride_context.get(key) for key in FIXED):
        raise ValueError('comparison fixed source condition differs')
    if (walk_context.get('controlled_behavior') != 'walk_cycle' or
            ride_context.get('controlled_behavior') != 'mounted_sidewalk'):
        raise ValueError('comparison deliberate behavior source missing')
    outputs = [measure(*sources) for sources in (walk_sources, ride_sources)]
    walk, ride = outputs
    if walk['frames'] != ride['frames'] or walk['frames'] != 600:
        raise ValueError('comparison capture duration differs')
    if not walk['operator_cycle_association_source_complete']:
        raise ValueError('comparison walking operator association missing')
    return {'format': 'worker-comparison-source-preaudit', 'passed': True,
            'physical_acceptance_claimed': False,
            'fixed_conditions': list(FIXED) + ['600 frames', '20 Hz', 'four synchronized cameras'],
            'deliberate_difference': 'walk_cycle versus mounted_sidewalk',
            'walk_mounted_moving_sidewalk_frames': walk['mounted_moving_sidewalk_frames'],
            'ride_mounted_moving_sidewalk_frames': ride['mounted_moving_sidewalk_frames'],
            'walk_operator_cycle_max_separation_m': walk['operator_cycle_separation_max_m'],
            'physical_review_required': True,
            'visual_posture_source_required': True,
            'geographic_identity_source_required': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--walk-poses', required=True)
    parser.add_argument('--walk-context', required=True)
    parser.add_argument('--walk-frame-map', required=True)
    parser.add_argument('--ride-poses', required=True)
    parser.add_argument('--ride-context', required=True)
    parser.add_argument('--ride-frame-map', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(
        (args.walk_poses, args.walk_context, args.walk_frame_map),
        (args.ride_poses, args.ride_context, args.ride_frame_map)), sort_keys=True))
