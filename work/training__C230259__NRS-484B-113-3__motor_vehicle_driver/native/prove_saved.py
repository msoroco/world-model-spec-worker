"""Synthetic saved-shape diagnostics for backing/moving traffic measurement."""
import json
import tempfile
from pathlib import Path
import os

from measure_motion import CAMERAS,measure
from measure_pedestrian import measure_pedestrian
from audit import audit_attempt,audit_comparison


def actor(x,y,vx,vy):
    return {'center_xy_m':[x,y],'velocity_xy_mps':[vx,vy],
        'body_xy_m':[[x-2,y-1],[x+2,y-1],[x+2,y+1],[x-2,y+1]]}


def fixture(path,early,reviewed=True,pedestrian=False):
    path.mkdir()
    context={'source_kind':'original_native','cell_id':'C230259',
        'conflict_region':{'x_min_m':8,'x_max_m':16,'y_min_m':-5,'y_max_m':-1},
        'other_highway_use_reviewed':reviewed,'driver_control_reviewed':reviewed,
        'pedestrian_presence_reviewed':True,'pedestrian_actor_count_at_start':int(pedestrian),
        'section_stem_recovered':True,
        'fixture_kind':'synthetic_diagnostic_only'}
    (path/'traffic-context.json').write_text(json.dumps(context)+'\n')
    start,end=(55,145) if early else (245,335)
    with (path/'native-motion.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native=index+100;active=start<=index<end
            progress=max(0,min(index-start,90));ego=actor(23-progress*.125,-7+progress*.04,-2.5 if active else 0,.8 if active else 0)
            other=actor(-35+min(index,300)*.3,-3,6 if index<300 else 0,0)
            walker=actor(12,4-max(0,min(index-50,250))*.04,0,-.8 if 50<=index<300 else 0) if pedestrian else None
            motion.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'ego':ego,'other':other,'pedestrian':walker,'backing_commanded':active})+'\n')
            frames.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory(dir=Path(os.environ['TMPDIR'])) as temporary:
        root=Path(temporary);late=root/'late';early=root/'early';unreviewed=root/'unreviewed'
        pedlate=root/'pedlate';pedearly=root/'pedearly'
        fixture(late,False);fixture(early,True);fixture(unreviewed,True,False)
        fixture(pedlate,False,pedestrian=True);fixture(pedearly,True,pedestrian=True)
        a,b=measure(late),measure(early)
        pa,pb=measure_pedestrian(pedlate),measure_pedestrian(pedearly)
        assert pa['pedestrian_moving_frame_count']==pb['pedestrian_moving_frame_count']==250
        assert pa['simultaneous_backing_and_pedestrian_motion_frame_count']==55
        assert pb['simultaneous_backing_and_pedestrian_motion_frame_count']==90
        assert audit_attempt(pedlate,pa)['source_bindings_passed']
        (pedearly/'traffic-context.json').write_text(json.dumps({**json.loads((pedearly/'traffic-context.json').read_text()),
            'pedestrian_actor_count_at_start':0})+'\n')
        try:measure_pedestrian(pedearly)
        except ValueError as error:assert 'pedestrian presence source missing' in str(error)
        else:raise AssertionError('Missing original pedestrian accepted')
        assert a['backing_frame_count']==90 and b['backing_frame_count']==90
        assert a['simultaneous_backing_and_other_moving_frame_count']==55
        assert b['simultaneous_backing_and_other_moving_frame_count']==90
        assert a['right_of_way_verdict']==b['right_of_way_verdict']=='unresolved'
        assert audit_attempt(late,a)['source_bindings_passed']
        fixed={'cell_id':'C230259','law_id':'NRS-484B-113-3','actor':'motor_vehicle_driver',
            'duration_s':30,'rate_hz':20,'cameras':list(CAMERAS)}
        assert audit_comparison(a,b,{**fixed,'case_suffix':'controlled_1'},
            {**fixed,'case_suffix':'controlled_2'})['declared_difference']=='backing onset timing'
        try:audit_comparison(a,b,{**fixed,'case_suffix':'controlled_1'},
            {**fixed,'case_suffix':'controlled_2','rate_hz':10})
        except ValueError as error:assert 'fixed condition' in str(error)
        else:raise AssertionError('Changed capture rate accepted')
        try:audit_attempt(late,{**a,'source_sha256':{**a['source_sha256'],'native-motion.jsonl':'0'*64}})
        except ValueError as error:assert 'hash mismatch' in str(error)
        else:raise AssertionError('Changed original source accepted')
        try:measure(unreviewed)
        except ValueError as error:assert 'unreviewed' in str(error)
        else:raise AssertionError('Unreviewed highway use accepted')
        (early/'reference_corner.mkv').unlink()
        try:measure(early)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        (late/'traffic-context.json').write_text(json.dumps({**json.loads((late/'traffic-context.json').read_text()),
            'section_stem_recovered':False})+'\n')
        try:measure(late)
        except ValueError as error:assert 'section source unreviewed' in str(error)
        else:raise AssertionError('Unreviewed parent source accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,'late_simultaneous_frames':55,
            'early_simultaneous_frames':90,'unreviewed_highway_use_rejected':True,
            'missing_camera_rejected':True,'unreviewed_parent_source_rejected':True,
            'source_hash_rejected':True,'comparison_fixed_condition_rejected':True,
            'pedestrian_alternative_passed':True,'missing_pedestrian_rejected':True,
            'right_of_way_verdict':'unresolved',
            'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
