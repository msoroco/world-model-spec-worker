"""Source-bound requests for separate pedestrian and concurrent-indication branches.

These rows are construction targets. They never certify a pedestrian's lawful
status, signal governance, actual pixels, cautiousness or legal compliance.
"""
import json

FRAMES = 600
RATE = 20
BRANCHES = {
    'pedestrian_clearance': {'branch': 'pedestrian_yield', 'release_frame': 320,
                             'movement': 'right', 'concurrent_left': False},
    'pedestrian_overlap': {'branch': 'pedestrian_yield', 'release_frame': 200,
                           'movement': 'right', 'concurrent_left': False},
    'concurrent_absent': {'branch': 'concurrent_indication', 'release_frame': 220,
                          'movement': 'left', 'concurrent_left': False},
    'concurrent_present': {'branch': 'concurrent_indication', 'release_frame': 220,
                           'movement': 'left', 'concurrent_left': True},
}


def rows(case):
    if case not in BRANCHES:
        raise ValueError('Unknown statutory branch request')
    config = BRANCHES[case]
    result = []
    for frame in range(FRAMES):
        t = frame / RATE
        # Adjacent crosswalk spans the south approach at y=-5. The source
        # rows request a walker traversal during the ego's arrival interval.
        pedestrian_x = min(5.0, -5.0 + max(0, frame - 170) * 0.10)
        pedestrian_y = -5.0
        pedestrian = ([round(pedestrian_x, 6), pedestrian_y]
                      if config['branch'] == 'pedestrian_yield' else None)
        pedestrian_inside = pedestrian is not None and -3.5 <= pedestrian_x <= 3.5
        if config['movement'] == 'right':
            ego_x = -1.75 if frame < config['release_frame'] else min(
                7.0, -1.75 + (frame - config['release_frame']) * 0.10)
            ego_y = -5.0 if frame < config['release_frame'] else min(
                0.0, -5.0 + (frame - config['release_frame']) * 0.10)
        else:
            ego_x = max(-12.0, -1.75 - max(0, frame - config['release_frame']) * 0.10)
            ego_y = min(4.0, -5.0 + max(0, frame - config['release_frame']) * 0.10)
        result.append({
            'frame': frame, 'time_s': t,
            'requested_ego_xy_m': [round(ego_x, 6), round(ego_y, 6)],
            'requested_pedestrian_xy_m': pedestrian,
            'requested_pedestrian_in_adjacent_crosswalk': pedestrian_inside,
            'requested_other_xy_m': [35.0, 1.75],
            'requested_arrow': {'direction': 'right',
                                'flashing_yellow_lit': frame % 20 < 10,
                                'governs_ego': 'requested_unverified'},
            'requested_concurrent_left_indication': config['concurrent_left'],
            'requested_movement': config['movement'],
            'requested_ego_release_frame': config['release_frame'],
            'pedestrian_lawful_status': None,
            'other_traffic_lawful_status': None,
            'cautiousness_legal_judgment': None,
            'original_native_observed': False})
    return result


def validate_pair(first, second, branch):
    if len(first) != FRAMES or len(second) != FRAMES:
        raise ValueError('Statutory branch frame inventory differs')
    for index, (a, b) in enumerate(zip(first, second)):
        if a['frame'] != index or b['frame'] != index or a['time_s'] != b['time_s']:
            raise ValueError('Statutory branch time base differs')
        for key in ('requested_arrow', 'requested_other_xy_m',
                    'requested_pedestrian_xy_m', 'requested_movement'):
            if a[key] != b[key]:
                raise ValueError('Fixed branch context differs: ' + key)
        if branch == 'pedestrian_yield':
            if a['requested_concurrent_left_indication'] != b['requested_concurrent_left_indication']:
                raise ValueError('Concurrent signal drifted in pedestrian pair')
        elif branch == 'concurrent_indication':
            if a['requested_ego_xy_m'] != b['requested_ego_xy_m']:
                raise ValueError('Ego route drifted in concurrent pair')
        else:
            raise ValueError('Unknown statutory branch comparison')
        for row in (a, b):
            if (row['pedestrian_lawful_status'] is not None
                    or row['other_traffic_lawful_status'] is not None
                    or row['cautiousness_legal_judgment'] is not None
                    or row['original_native_observed'] is not False):
                raise ValueError('Statutory request asserts unreviewed fact')
    if branch == 'pedestrian_yield':
        return {'branch': branch, 'changed': 'ego release relative to crosswalk traversal',
                'first_release': first[0]['requested_ego_release_frame'],
                'second_release': second[0]['requested_ego_release_frame']}
    return {'branch': branch, 'changed': 'concurrent left-turn indication request',
            'first_concurrent': first[0]['requested_concurrent_left_indication'],
            'second_concurrent': second[0]['requested_concurrent_left_indication']}


def proof():
    pedestrian = validate_pair(rows('pedestrian_clearance'), rows('pedestrian_overlap'),
                               'pedestrian_yield')
    concurrent = validate_pair(rows('concurrent_absent'), rows('concurrent_present'),
                               'concurrent_indication')
    if pedestrian['first_release'] == pedestrian['second_release']:
        raise AssertionError('Pedestrian comparison did not vary release')
    if concurrent['first_concurrent'] == concurrent['second_concurrent']:
        raise AssertionError('Concurrent comparison did not vary indication')
    return {'passed': True, 'native_executed': False,
            'legal_verdict_claimed': False,
            'pedestrian': pedestrian, 'concurrent': concurrent}


if __name__ == '__main__':
    print(json.dumps(proof(), sort_keys=True))
