"""Synthetic saved-shape diagnostics for a solid-white lane separator."""
import json
import tempfile
from pathlib import Path

from measure_separator import CAMERAS,measure


def fixture(path,cross,reviewed=True):
    path.mkdir()
    context={'source_kind':'original_native','cell_id':'C245532',
        'separator':{'y_m':-3.5,'x_min_m':-60,'x_max_m':60,'form':'solid','color':'white',
            'inner_lane_id':-1,'outer_lane_id':-2},
        'public_highway_reviewed':reviewed,'legal_controlled_access_reviewed':reviewed,
        'entrance_lane_function_reviewed':reviewed,'official_line_reviewed':reviewed,
        'vehicle_driver_scope_reviewed':False,'emergency_necessity_reviewed':False,
        'subsection_3_conditions_reviewed':False,'fixture_kind':'synthetic_diagnostic_only'}
    (path/'separator-context.json').write_text(json.dumps(context)+'\n')
    with (path/'native-motion.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native=index+100;progress=max(0,min(index-40,140))/140 if cross else 0
            x=-42+min(index,350)*.25;y=-5.25+3.5*progress
            body=[[x-2,y-.9],[x+2,y-.9],[x+2,y+.9],[x-2,y+.9]]
            motion.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'ego':{'center_xy_m':[x,y],'body_xy_m':body},
                'lane_id':-1 if y>-3.5 else -2})+'\n')
            frames.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);stay=root/'stay';cross=root/'cross';unreviewed=root/'unreviewed'
        fixture(stay,False);fixture(cross,True);fixture(unreviewed,True,False)
        a,b=measure(stay),measure(cross)
        assert a['body_straddle_frame_count']==0 and a['first_traffic_side_center_frame'] is None
        assert b['body_straddle_frame_count']>0 and b['first_traffic_side_center_frame'] is not None
        assert b['native_lane_ids_seen']==[-2,-1] and b['crossing_verdict']=='unresolved'
        pending=measure(unreviewed)
        assert pending['source_context_review_pending'] and pending['crossing_verdict']=='unresolved'
        context_path=unreviewed/'separator-context.json'
        context=json.loads(context_path.read_text());context.pop('official_line_reviewed')
        context_path.write_text(json.dumps(context)+'\n')
        try:measure(unreviewed)
        except ValueError as error:assert 'review status missing' in str(error)
        else:raise AssertionError('Missing original review status accepted')
        (cross/'traffic_view.mkv').unlink()
        try:measure(cross)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,
            'stay_straddle_frames':a['body_straddle_frame_count'],
            'cross_straddle_frames':b['body_straddle_frame_count'],
            'cross_first_traffic_center_frame':b['first_traffic_side_center_frame'],
            'unreviewed_controlled_access_retained_as_pending':True,
            'missing_review_status_rejected':True,'missing_camera_rejected':True,
            'statutory_crossing_cutoff_adopted':False,'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
