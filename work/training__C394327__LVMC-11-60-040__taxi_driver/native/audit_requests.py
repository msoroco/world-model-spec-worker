"""Independent exact comparison of taxi loading draft requests."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

BASE = Path(__file__).resolve().parents[1]
SOURCE = Path(__file__).resolve().parent
PREFIX = BASE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((BASE/'draft-native-manifest.json').read_text())
    assert manifest['assignment_id'] == PREFIX
    assert manifest['status'] == 'draft_not_selected'
    assert [c['case_id'] for c in manifest['cases']] == [PREFIX+'__probe_a', PREFIX+'__probe_b']
    road = ET.fromstring((SOURCE/'taxi-road.xodr').read_text()).find('road')
    assert road.find('./planView/geometry/line') is not None
    assert road.find('./objects/object').get('id') == '701'
    assert road.find('./signals/signal').get('name') == 'TAXI STAND'
    pair = []
    for case in manifest['cases']:
        path = BASE/case['construction']
        assert sha(path) == case['construction_sha256']
        construction = json.loads(path.read_text())
        files = {f['path']: f['content'] for f in construction['files']}
        config = json.loads(files['config.json'])
        rows = [json.loads(s) for s in files['requested-track.jsonl'].splitlines()]
        assert len(rows) == 600
        assert all(row['frame'] == i and row['time_s'] == (i+1)/20 for i,row in enumerate(rows))
        assert all(row['requested_stand_location'] == 'outside_designated_stand' for row in rows)
        assert all(row['requested_taxi_identity'] is True for row in rows)
        assert all(row['requested_speed_mps'] == 0 for row in rows)
        assert all(row['requested_center_xy_m'] == [5.25,10] for row in rows)
        assert config['road_sha256'] == sha(SOURCE/'taxi-road.xodr')
        assert config['physical_completion'] is False and config['legal_verdict'] is None
        assert len(config['cameras']) == 4
        pair.append((config,rows))
    a,b = pair
    assert {k:v for k,v in a[0].items() if k not in ('case_id','requested_activity')} == {
        k:v for k,v in b[0].items() if k not in ('case_id','requested_activity')}
    difference = {'requested_activity','requested_occupant_count'}
    assert all({k:v for k,v in a[1][i].items() if k not in difference} ==
               {k:v for k,v in b[1][i].items() if k not in difference}
               for i in range(600))
    assert a[0]['requested_activity'] == 'passenger_loading'
    assert b[0]['requested_activity'] == 'merchandise_loading'
    assert a[1][0]['requested_occupant_count'] == b[1][0]['requested_occupant_count'] == 2
    assert a[1][-1]['requested_occupant_count'] == 3
    assert b[1][-1]['requested_occupant_count'] == 2
    report = {'assignment_id':PREFIX,'comparison':'authored passenger versus merchandise request',
              'construction_sha256':{suffix:case['construction_sha256'] for suffix,case in
                                     zip(('probe_a','probe_b'),manifest['cases'])},
              'road_sha256':sha(SOURCE/'taxi-road.xodr'),
              'frames_per_case':600,'duration_s':30,'source_camera_count':4,
              'fixed_taxi_road_curb_speed_door_timing_and_cameras':True,
              'deliberate_differences':['requested_activity','requested_occupant_count'],
              'original_native_observed':False,'other_regulations_reviewed':False,
              'stand_designation_verified':False,'legal_verdict':None}
    (SOURCE/'request-comparison-proof.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    main()
