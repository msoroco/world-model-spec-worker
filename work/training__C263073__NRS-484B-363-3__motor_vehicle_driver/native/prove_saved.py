"""Synthetic saved-shape diagnostics for school-zone turn measurement."""
import json
import hashlib
import tempfile
from pathlib import Path

from layout import ZONE,TURN,planned_pose
from measure_turn import CAMERAS,measure
from review_context import REQUIRED, EXCEPTIONS, EXCEPTION_TOPICS


def fixture(path,turn,reviewed=True):
    path.mkdir()
    context={'source_kind':'original_native','cell_id':'C263073','zone':ZONE,'turn':TURN,
        'zone_designation_reviewed':reviewed,'school_adjacency_reviewed':reviewed,
        'highway_status_reviewed':reviewed,'child_identity_and_presence_reviewed':reviewed,
        'session_operation_civil_time_reviewed':False,'class_hours_reviewed':False,
        'beacon_and_sign_state_reviewed':False,'all_five_exceptions_reviewed':False,
        'path_is_kinematic':True,'fixture_kind':'synthetic_diagnostic_only'}
    if reviewed:
        records={}
        for topic in REQUIRED:
            source=path/(topic+'.json')
            source.write_text(json.dumps({'topic':topic,'synthetic_fixture':True})+'\n')
            records[topic]={'topic':topic,'path':source.name,
                'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'reviewer':'synthetic-test','observation':'Synthetic shape fixture only'}
        context['independent_review']={'format':'c263073-source-review-v1','records':records,
            'exception_dispositions':{name:{'status':'unresolved',
                'source_topics':sorted(EXCEPTION_TOPICS[name]),
                'reason':'Synthetic fixture does not resolve legal applicability'} for name in EXCEPTIONS}}
    (path/'school-context.json').write_text(json.dumps(context)+'\n')
    with (path/'native-motion.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            native=index+100;x,y,heading=planned_pose(index,turn)
            motion.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'ego':{'center_xy_m':[x,y],'heading_deg':heading},
                'other_person':{'center_xy_m':[4,7.5]},'kinematic_path_only':True})+'\n')
            frames.write(json.dumps({'native_frame':native,'video_frame':index,'time_s':index/20,
                'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);straight=root/'straight';turn=root/'turn';unreviewed=root/'unreviewed'
        fixture(straight,False);fixture(turn,True);fixture(unreviewed,True,False)
        a,b=measure(straight),measure(turn)
        assert a['cumulative_absolute_heading_change_deg']==0
        assert abs(b['cumulative_absolute_heading_change_deg']-180)<1e-6
        assert b['other_person_zone_frame_count']==600 and b['u_turn_legal_verdict']=='unresolved'
        try:measure(unreviewed)
        except ValueError as error:assert 'Independent school-zone source review missing' in str(error)
        else:raise AssertionError('Unreviewed school zone accepted')
        (turn/'child_area.mkv').unlink()
        try:measure(turn)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,
            'straight_heading_change_deg':0,'turn_heading_change_deg':180,
            'person_zone_frames':600,'unreviewed_zone_rejected':True,
            'missing_camera_rejected':True,'u_turn_legal_verdict':'unresolved',
            'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
