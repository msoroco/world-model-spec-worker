"""CPU source-shape proof for both red-X lane conditions and missing evidence."""
import copy
import json
from lane_red_x_meter import measure


def source_rows(enter):
    out = []
    for index in range(600):
        center_y = -5.25
        if enter:
            center_y += 3.5 * min(1, max(0, (index - 200) / 100))
        vertices = [[10 + index * .125 + dx, center_y + dy, z]
                    for dx in (-1, 1) for dy in (-.8, .8) for z in (0, 1)]
        out.append({
            'frame': index, 'native_frame': 1000 + index, 'time_s': index / 20,
            'source': 'native_post_tick',
            'signal': {'id': 100, 'source': 'native_signal_state',
                       'authority_source': 'map_signal_inventory',
                       'inventory_verified': True, 'official_authority_review_pending': True,
                       'mount_source': 'map_signal_transform', 'mount_m': [60, -1.75, 4.5],
                       'lane_id': -1, 'mount_lane_id': -1, 'indication': 'red_x',
                       'facing_yaw_deg': 0},
            'vehicle': {'source': 'native_actor_pose', 'lane_source': 'map_waypoint_projection',
                        'body_vertices_m': vertices, 'lane_id': -1 if center_y > -3.5 else -2,
                        'proposed_lane_id': -1 if enter else -2, 'yaw_deg': 0}
        })
    return out

def main():
    outside = measure({'frames': source_rows(False)})
    entry_rows = source_rows(True)
    entry = measure({'frames': entry_rows})
    assert outside['red_x_facing_frames'] == 600 and outside['governed_lane_overlap_frames'] == 0
    assert entry['red_x_facing_frames'] == 600 and entry['first_governed_lane_overlap_frame'] is not None
    assert entry['governed_lane_wholly_inside_frames'] > 0
    for label, edit, error in (
        ('missing signal provenance', lambda rows: rows[1]['signal'].pop('source'), 'provenance'),
        ('generic indication', lambda rows: rows[1]['signal'].__setitem__('indication', 'green_down_arrow'), 'red-X'),
        ('wrong governed lane', lambda rows: rows[1]['signal'].__setitem__('lane_id', -2), 'governed lane'),
        ('missing actor body', lambda rows: rows[1]['vehicle'].pop('body_vertices_m'), 'body vertices'),
        ('frame discontinuity', lambda rows: rows[1].__setitem__('native_frame', 1004), 'frame identity'),
    ):
        damaged = copy.deepcopy(entry_rows)
        edit(damaged)
        try:
            measure({'frames': damaged})
        except ValueError as exc:
            assert error in str(exc), (label, str(exc))
        else:
            raise AssertionError('did not reject ' + label)
    print(json.dumps({'outside_overlap_frames': outside['governed_lane_overlap_frames'],
                      'entry_first_overlap_frame': entry['first_governed_lane_overlap_frame'],
                      'entry_wholly_inside_frames': entry['governed_lane_wholly_inside_frames'],
                      'negative_source_variants_rejected': 5,
                      'physical_observation_claimed': False}, sort_keys=True))

if __name__ == '__main__':
    main()
