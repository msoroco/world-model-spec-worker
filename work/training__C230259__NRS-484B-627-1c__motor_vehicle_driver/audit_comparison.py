"""Independently compare original route sources without a legal conclusion."""
import argparse
import hashlib
import json
from pathlib import Path

from route_measure import measure

NAMES = ('route-trace.jsonl', 'route-context.json', 'road.xodr', 'video_frames.jsonl')


def require(value, message):
    if not value:
        raise ValueError(message)


def load(folder):
    folder = Path(folder)
    raw = [(folder / name).read_bytes() for name in NAMES]
    measured = measure(*raw)
    context = json.loads(raw[1])
    rows = [json.loads(line) for line in raw[0].splitlines()]
    return {'raw': raw, 'measured': measured, 'context': context, 'rows': rows,
            'hashes': {name: hashlib.sha256(data).hexdigest()
                       for name, data in zip(NAMES, raw)}}


def compare(first, second, mode):
    a, b = load(first), load(second)
    ca, cb = a['context'], b['context']
    require(ca['assignment_id'] == cb['assignment_id'], 'Comparison assignment changed')
    require(ca['source_kind'] == cb['source_kind'], 'Comparison source kind changed')
    require(ca['source_kind'] == 'synthetic_fixture', 'Diagnostic proof requires synthetic fixture')
    require(ca['controlled_access_designation_independently_verified'] is False
            and cb['controlled_access_designation_independently_verified'] is False,
            'Unexpected controlled-access legal claim')
    require(len(a['rows']) == len(b['rows']) == 900, 'Comparison duration differs')
    require(ca['planned_alternate_possible'] is True, 'Reference route must contain an alternate')
    for index, (x, y) in enumerate(zip(a['rows'], b['rows'])):
        require(x['video_frame'] == y['video_frame'] == index
                and x['time_s'] == y['time_s']
                and set(x['camera_native_frames']) == set(y['camera_native_frames']),
                'Comparison timing or camera policy changed')
        require(x['ego']['actor_id'] == y['ego']['actor_id']
                and [p['actor_id'] for p in x['following']] == [p['actor_id'] for p in y['following']],
                'Comparison participant set changed')
        if index < 20:
            require(x['ego']['road_id'] == y['ego']['road_id'] == 1
                    and [p['road_id'] for p in x['following']] ==
                    [p['road_id'] for p in y['following']],
                    'Comparison approach context changed')
    if mode == 'route_choice':
        require(a['raw'][2] == b['raw'][2], 'Route-choice comparison map changed')
        require(ca['planned_take_alternate'] is True and cb['planned_take_alternate'] is False,
                'Route-choice controller contrast changed')
        require(cb['planned_alternate_possible'] is True, 'Route-choice availability changed')
        require(a['measured']['observed_alternate_road'] is True
                and b['measured']['observed_alternate_road'] is False,
                'Route-choice contrast absent from original rows')
    elif mode == 'route_availability':
        require(ca['planned_take_alternate'] is False
                and cb['planned_take_alternate'] is False,
                'Availability comparison controller changed')
        require(cb['planned_alternate_possible'] is False
                and a['raw'][2] != b['raw'][2], 'Availability map contrast absent')
        require(a['measured']['authored_alternate_connected'] is True
                and b['measured']['authored_alternate_connected'] is False,
                'Original route topology contrast absent')
        require(a['measured']['observed_alternate_road'] is False
                and b['measured']['observed_alternate_road'] is False,
                'Availability pair changed subject request')
    else:
        raise ValueError('Unknown comparison mode')
    return {'format': 'c230259-independent-route-comparison-v1',
            'source_kind': 'synthetic_fixture', 'mode': mode,
            'left_source_sha256': a['hashes'], 'right_source_sha256': b['hashes'],
            'fixed_source_checks_passed': True, 'authored_contrast_observed': True,
            'original_native_capture_attested': False,
            'controlled_access_designation_independently_verified': False,
            'impediment_legally_determined': False,
            'practical_route_availability_legally_determined': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--mode', choices=('route_choice', 'route_availability'), required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.left, args.right, args.mode), sort_keys=True))
