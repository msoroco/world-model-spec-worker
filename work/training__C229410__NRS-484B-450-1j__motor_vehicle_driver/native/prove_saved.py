"""Synthetic saved-shape diagnostics for source-bound entrance measurement."""
import json
import tempfile
from pathlib import Path

from measure_entrance import CAMERAS,measure


def fixture(path,target,reviewed=True):
    path.mkdir()
    context={'source_kind':'original_native','cell_id':'C229410',
        'entrance':{'x_min_m':-3,'x_max_m':3,'road_edge_y_m':-4,'road_side':'south'},
        'fire_station_identity_reviewed':reviewed,'driveway_entrance_reviewed':reviewed,
        'highway_side_reviewed':reviewed,'parking_activity_reviewed':False,
        'traffic_conflict_reviewed':False,'law_officer_device_direction_reviewed':False,
        'fixture_kind':'synthetic_diagnostic_only'}
    (path/'entrance-context.json').write_text(json.dumps(context)+'\n')
    with (path/'native-vehicle.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native=index+100
            x=-40+(target+40)*min(index,300)/300
            body=[[x-2,-3],[x+2,-3],[x+2,-1],[x-2,-1]]
            motion.write(json.dumps({'native_frame':native,'video_frame':index,
                'time_s':index/20,'body_xy_m':body,'speed_mps':4 if index<300 else 0})+'\n')
            frames.write(json.dumps({'native_frame':native,'video_frame':index,
                'time_s':index/20,'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);outside=root/'outside';inside=root/'inside';unreviewed=root/'unreviewed'
        fixture(outside,17);fixture(inside,3);fixture(unreviewed,3,False)
        a,b=measure(outside),measure(inside)
        assert a['stationary_min_body_edge_gap_m']==12
        assert b['stationary_min_body_edge_gap_m']==0
        assert b['twenty_foot_clause_verdict']=='unresolved'
        assert b['statutory_reference_point_method_adopted'] is False
        try:measure(unreviewed)
        except ValueError as error:assert 'unreviewed' in str(error)
        else:raise AssertionError('Unreviewed station accepted')
        (inside/'entrance.mkv').unlink()
        try:measure(inside)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,
            'outside_raw_body_edge_gap_m':12,'inside_raw_body_edge_gap_m':0,
            'unreviewed_station_rejected':True,'missing_camera_rejected':True,
            'statutory_distance_method_adopted':False,'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
