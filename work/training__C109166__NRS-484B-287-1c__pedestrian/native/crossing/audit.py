"""Independently audit isolation of the two authored 30-second requests."""
import json

from request import CASES, CASE, FRAMES, HERE, sha


def audit():
    paths = [HERE / 'drafts' / name / 'requested-tracks.jsonl' for name in CASES]
    left, right = [[json.loads(line) for line in p.read_text().splitlines()]
                   for p in paths]
    if len(left) != FRAMES or len(right) != FRAMES:
        raise AssertionError('Unexpected request length')
    allowed = {'requested_x_m', 'requested_crossing_location'}
    for a, b in zip(left, right):
        if {k for k in a if a[k] != b[k]} != allowed:
            raise AssertionError('Uncontrolled request difference')
        if (a['intersection_a_x_m'], a['intersection_b_x_m'],
                a['marked_crosswalk_x_m']) != (0, 100, 40):
            raise AssertionError('Authored map markers changed')
        if not 0 < a['requested_x_m'] < 100 or not 0 < b['requested_x_m'] < 100:
            raise AssertionError('Crossing request outside authored segment')
    entry = [next(i for i, row in enumerate(rows) if row['requested_y_m'] >= -4)
             for rows in (left, right)]
    if entry != [259, 259]:
        raise AssertionError('Road entry timing differs')
    receipt = {'format': 'c109166-request-comparison-v1',
               'assignment_id': CASE.name, 'compared_frames': FRAMES,
               'controlled_difference': sorted(allowed),
               'common_roadway_entry_frame': entry[0],
               'track_sha256': {name: sha(path) for name, path in zip(CASES, paths)},
               'native_geometry_verified': False,
               'official_devices_operating_verified': False,
               'delivery_ready': False}
    (HERE / 'comparison-audit.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    value = audit()
    print(json.dumps({'compared_frames': value['compared_frames']}))
