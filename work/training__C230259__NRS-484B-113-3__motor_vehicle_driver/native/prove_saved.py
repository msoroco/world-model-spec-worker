"""Synthetic saved-shape diagnostics for backing/moving traffic measurement."""
import json
import tempfile
from pathlib import Path

from measure_motion import CAMERAS,measure


def actor(x,y,vx,vy):
    return {'center_xy_m':[x,y],'velocity_xy_mps':[vx,vy],
        'body_xy_m':[[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]}


def fixture(path,early,reviewed=True):
    path.mkdir()
    context={'source_kind':'original_native','cell_id':'C230259',
        'conflict_region':{'x_min_m':8,'x_max_m':16,'y_min_m':-5,'y_max_m':-1},
        'other_highway_use_reviewed':reviewed,'driver_control_reviewed':reviewed,
        'pedestrian_presence_reviewed':False,'section_stem_recovered':False,
        'fixture_kind':'synthetic_diagnostic_only'}
    (path/'traffic-context.json').write_text(json.dumps(context)+'\n')
    start,end=(55,145) if early else (245,335)
    with (path/'native-motion.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native=index+100;active=start<=index<end
            progress=max(0,min(index-start,90));ego=actor(23-progress*.125,-7+progress*.04,-2.5 if active else 0,.8 if active else 0)
            other=actor(-35+min(index,300)*.3,-3,6 if index<300 else 0,0)
            motion.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'ego':ego,'other':other,'backing_commanded':active})+'\n')
            frames.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);late=root/'late';early=root/'early';unreviewed=root/'unreviewed'
        fixture(late,False);fixture(early,True);fixture(unreviewed,True,False)
        a,b=measure(late),measure(early)
        assert a['backing_frame_count']==90 and b['backing_frame_count']==90
        assert a['simultaneous_backing_and_other_moving_frame_count']==55
        assert b['simultaneous_backing_and_other_moving_frame_count']==90
        assert a['right_of_way_verdict']==b['right_of_way_verdict']=='unresolved'
        try:measure(unreviewed)
        except ValueError as error:assert 'unreviewed' in str(error)
        else:raise AssertionError('Unreviewed highway use accepted')
        (early/'traffic_view.mkv').unlink()
        try:measure(early)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,'late_simultaneous_frames':55,
            'early_simultaneous_frames':90,'unreviewed_highway_use_rejected':True,
            'missing_camera_rejected':True,'right_of_way_verdict':'unresolved',
            'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
