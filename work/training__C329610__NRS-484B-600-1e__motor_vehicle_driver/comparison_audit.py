"""Independent source-bound comparison of three left-turn absolute-speed cases."""
import argparse
import hashlib
import json
from pathlib import Path
from speed_measure import measure

AID = 'training__C329610__NRS-484B-600-1e__motor_vehicle_driver'
PROBES = ('probe_a', 'probe_at', 'probe_b')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(directories, diagnostic=False, omit=None):
    if len(directories) != 3:
        raise ValueError('Three exact C329610 speed cases required')
    rows = []
    fixed = None
    for suffix, directory in zip(PROBES, directories):
        case = AID+'__'+suffix
        root = Path(directory)
        if omit:
            raise ValueError('Missing saved comparison source: '+omit)
        for name in ('road.xodr','config.json','native_motion.jsonl','video_frames.jsonl',
                     'road_context.json', *(camera+'.mkv' for camera in CAMERAS)):
            if not (root/name).is_file():
                raise ValueError('Missing saved comparison source: '+name)
        config, context = read(root/'config.json'), read(root/'road_context.json')
        if (config.get('case_id') != case or context.get('case_id') != case or
                config.get('law_id') != 'NRS-484B-600-1e' or
                config.get('cell_id') != 'C329610' or
                config.get('actor') != 'motor_vehicle_driver'):
            raise ValueError('Exact frozen case, law, cell or actor differs')
        kind = 'synthetic_diagnostic' if diagnostic else 'original_source_review'
        if context.get('review_kind') != kind:
            raise ValueError('Original/diagnostic source classification differs')
        observed = measure(root)
        if (observed['sample_count'] != 600 or observed['left_turn_road_ids'] != [1,13,4] or
                observed['statutory_cap_mph'] != 80 or observed['posted_limit_required'] is not False):
            raise ValueError('Full original speed and left-turn measurement differs')
        camera_contract = tuple((row['name'],row['width'],row['height']) for row in config['cameras'])
        common = (sha(root/'road.xodr'), camera_contract, config['rate_hz'],
                  config['duration_s'], context['route_source'],
                  context['vehicle_identity_source'], context['driving_state_source'])
        if fixed is None:
            fixed = common
        elif fixed != common:
            raise ValueError('Comparison road, route, camera or role source changed')
        rows.append({'case_id': case, 'requested_speed_mph': config['requested_speed_mph'],
                     'maximum_observed_mph': observed['maximum_observed_mph_while_driving'],
                     'frames_above_80_mph': len(observed['frames_above_80_mph']),
                     'native_motion_sha256': sha(root/'native_motion.jsonl'),
                     'road_context_sha256': sha(root/'road_context.json')})
    if [row['requested_speed_mph'] for row in rows] != [75,80,85]:
        raise ValueError('Declared below/at/above controller contrast differs')
    if len({row['native_motion_sha256'] for row in rows}) != 3:
        raise ValueError('Comparison cases share one motion source')
    return {'format': 'worker-speed-comparison-audit', 'assignment_id': AID,
            'comparison_id': AID+'__comparison', 'source_kind': kind,
            'fixed_conditions': ['C329610 two-way left-turn road and route 1,13,4',
                                 'motor_vehicle_driver subject identity policy',
                                 '30 s at 20 Hz and four source-camera contract'],
            'deliberate_difference': 'requested approach speed 75/80/85 mph',
            'cases': rows, 'observed_relation_to_80_mph': [
                'above' if row['maximum_observed_mph'] > 80 else
                'below' if row['maximum_observed_mph'] < 80 else 'equal_sample'
                for row in rows],
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dirs', nargs=3, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source')
    args = parser.parse_args()
    report = audit(args.source_dirs, args.diagnostic, args.omit_source)
    path = Path(args.output)
    if path.exists():
        raise ValueError('Retain prior comparison audit result')
    path.write_text(json.dumps(report, indent=2)+'\n')
