"""Independent comparison of the two authored angle-parking requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).resolve().parent
PREFIX = BASE.name


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((BASE / 'draft-native-manifest.json').read_text())
    assert manifest['assignment_id'] == PREFIX
    assert manifest['status'] == 'draft_not_selected'
    assert [c['case_id'] for c in manifest['cases']] == [
        PREFIX + '__probe_a', PREFIX + '__probe_b']
    road_path = NATIVE / 'angle-bay-road.xodr'
    road = ET.fromstring(road_path.read_text()).find('road')
    assert road.get('length') == '140'
    assert road.find('./planView/geometry').get('hdg') == '1.5707963267948966'
    assert road.find('./planView/geometry/line') is not None
    assert {lane.get('id'): lane.get('type') for lane in
            road.findall('./lanes/laneSection/right/lane')} == {
                '-1': 'driving', '-2': 'parking', '-3': 'sidewalk'}
    assert not road.findall('./lanes/laneSection/left/lane')
    assert any(o.get('type') == 'parkingSpace' and o.get('id') == '901'
               for o in road.findall('objects/object'))
    assert any(s.get('name') == 'ANGLE PARKING'
               for s in road.findall('signals/signal'))
    pair = []
    for case in manifest['cases']:
        path = BASE / case['construction']
        assert digest(path) == case['construction_sha256']
        construction = json.loads(path.read_text())
        files = {f['path']: f['content'] for f in construction['files']}
        config = json.loads(files['config.json'])
        rows = [json.loads(line) for line in files['requested-track.jsonl'].splitlines()]
        assert len(rows) == 600
        assert all(row['frame'] == i and row['time_s'] == (i+1)/20
                   for i, row in enumerate(rows))
        assert len({tuple(row['ego_center_xy_m']) for row in rows}) == 1
        assert len({row['ego_front_yaw_deg'] for row in rows}) == 1
        assert all(row['ego_speed_mps'] == 0 for row in rows)
        assert config['road_sha256'] == digest(road_path)
        assert config['permission_source_required'] is True
        assert config['original_activity_source_required'] is True
        assert config['physical_completion'] is False
        assert config['legal_verdict'] is None
        assert len(config['cameras']) == 4
        pair.append((config, rows, construction, files))
    a, b = pair
    for index in (0, 1):
        x, y = a[1][index], b[1][index]
        assert {k: v for k, v in x.items() if k != 'ego_front_yaw_deg'} == {
            k: v for k, v in y.items() if k != 'ego_front_yaw_deg'}
    assert all({k: v for k, v in a[1][i].items() if k != 'ego_front_yaw_deg'} ==
               {k: v for k, v in b[1][i].items() if k != 'ego_front_yaw_deg'}
               for i in range(600))
    assert {k: v for k, v in a[0].items() if k not in
            ('case_id', 'requested_front_yaw_deg')} == {
                k: v for k, v in b[0].items() if k not in
                ('case_id', 'requested_front_yaw_deg')}
    assert a[0]['requested_front_yaw_deg'] == 45
    assert b[0]['requested_front_yaw_deg'] == 225
    report = {
        'assignment_id': PREFIX,
        'comparison': 'authored request orientation only',
        'road_sha256': digest(road_path),
        'construction_sha256': {suffix: digest(BASE / case['construction'])
                                for suffix, case in zip(('probe_a', 'probe_b'), manifest['cases'])},
        'frames_per_case': 600,
        'duration_s': 30,
        'source_camera_count': 4,
        'same_road_bay_center_speed_and_camera_geometry': True,
        'only_control_difference': 'ego front yaw 45 versus 225 degrees',
        'original_native_observed': False,
        'city_engineer_permission_verified': False,
        'actual_standing_or_parking_verified': False,
        'legal_verdict': None,
    }
    (NATIVE / 'request-comparison-proof.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
