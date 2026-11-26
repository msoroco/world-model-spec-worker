"""Compare two source-bound pedestrian departure cases without a legal verdict."""
import argparse
import hashlib
import json
from pathlib import Path
from native.crossing_meter import measure

AID = 'training__C190398__LVMC-11-30-060-B__pedestrian'
CASES = (AID+'__yield', AID+'__enter_ahead')
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def audit(directories, diagnostic=False, omit=None):
    if len(directories) != 2:
        raise ValueError('Two exact C190398 pedestrian cases required')
    if omit:
        raise ValueError('Missing saved comparison source: '+omit)
    records, fixed = [], None
    for case, location in zip(CASES, directories):
        root = Path(location)
        for name in ('road.xodr', 'config.json', 'post-tick.jsonl', 'video_frames.jsonl',
                     'crossing-context.json', *(camera+'.mkv' for camera in CAMERAS)):
            if not (root/name).is_file():
                raise ValueError('Missing saved comparison source: '+name)
        config, context = read(root/'config.json'), read(root/'crossing-context.json')
        if (config.get('case_id') != case or config.get('law_id') != 'LVMC-11-30-060-B' or
                config.get('cell_id') != 'C190398' or config.get('actor') != 'pedestrian' or
                context.get('frozen_cell') != {'layout':'pedestrian_overpass', 'maneuver':'straight', 'control':'other_vehicle'}):
            raise ValueError('Exact frozen case, law, cell or actor differs')
        kind = 'synthetic_scene_request' if diagnostic else 'native_post_tick'
        if context.get('source_kind') != kind:
            raise ValueError('Original/diagnostic source classification differs')
        measured = measure(root)
        if (measured['frames'] != 600 or measured['rate_hz'] != 20 or
                measured['overhead_crossing_at_entry'] is not True):
            raise ValueError('Overhead crossing measurement differs')
        if not diagnostic and context.get('designated_place_prohibition') is not False:
            raise ValueError('Section 11.30.070 designated-place source review absent')
        camera = tuple((item['name'], item['width'], item['height'], item['fov_deg'])
                       for item in config['cameras'])
        common = (sha(root/'road.xodr'), camera, config['rate_hz'], config['duration_s'],
                  context['pedestrian_id'], tuple(context['vehicle_ids']),
                  context['frozen_cell'], context['marked_crosswalk_intervals_y_m'],
                  context['intersection_intervals_y_m'])
        if fixed is None:
            fixed = common
        elif fixed != common:
            raise ValueError('Comparison road, participants, cameras or cell changed')
        records.append({'case_id': case, 'requested_departure_frame': config['pedestrian_departure_frame'],
                        'measured_entry_frame': measured['roadway_entry_frame'],
                        'vehicle_conflict_frames': measured['vehicle_conflict_frames'],
                        'precedence_at_entry': measured['precedence_at_entry'],
                        'post_tick_sha256': sha(root/'post-tick.jsonl'),
                        'crossing_context_sha256': sha(root/'crossing-context.json')})
    if [row['requested_departure_frame'] for row in records] != [320, 140]:
        raise ValueError('Declared pedestrian departure contrast differs')
    if len({row['post_tick_sha256'] for row in records}) != 2:
        raise ValueError('Comparison cases share one post-tick source')
    return {'format': 'worker-pedestrian-comparison-audit', 'assignment_id': AID,
            'comparison_id': AID+'__planned_comparison',
            'source_kind': 'synthetic_diagnostic' if diagnostic else 'original_source_review',
            'fixed_conditions': ['C190398 pedestrian_overpass/straight/other_vehicle cell',
                                 'same pedestrian and roadway vehicle identities',
                                 '30 s at 20 Hz and four source cameras'],
            'deliberate_difference': 'pedestrian requested departure frame 320 versus 140',
            'cases': records, 'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-dirs', nargs=2, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--omit-source')
    args = parser.parse_args()
    result = audit(args.source_dirs, args.diagnostic, args.omit_source)
    path = Path(args.output)
    if path.exists():
        raise ValueError('Retain prior comparison audit result')
    path.write_text(json.dumps(result, indent=2)+'\n')
