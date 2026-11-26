"""Synthetic saved-shape diagnostics for school-zone turn measurement."""
import json
import hashlib
import tempfile
from pathlib import Path

from layout import ZONE,TURN,planned_pose
from measure_turn import CAMERAS,measure
from review_context import REQUIRED, EXCEPTIONS, EXCEPTION_TOPICS
from finalize import run as finalize_run
from branch_cases import CASES


def fixture(path,turn,reviewed=True,suffix=None):
    path.mkdir()
    suffix = suffix or ('controlled_2' if turn else 'controlled_1')
    branch = CASES[suffix]
    if branch['turn'] != turn:
        raise ValueError('Selected fixture turn target differs')
    bundle=Path(__file__).resolve().parent/'bundles'/suffix/'construction.json'
    construction=json.loads(bundle.read_text())
    config=json.loads(next(item['content'] for item in construction['files'] if item['path']=='config.json'))
    (path/'config.json').write_text(json.dumps(config)+'\n')
    context={'source_kind':'original_native','cell_id':'C263073','zone':ZONE,'turn':TURN,
        'zone_designation_reviewed':reviewed,'school_adjacency_reviewed':reviewed,
        'highway_status_reviewed':reviewed,'child_identity_and_presence_reviewed':reviewed,
        'session_operation_civil_time_reviewed':False,'class_hours_reviewed':False,
        'beacon_and_sign_state_reviewed':False,'all_five_exceptions_reviewed':False,
        'path_is_kinematic':False,'fixture_kind':'synthetic_diagnostic_only'}
    if reviewed:
        records={}
        (path/'review-sources').mkdir()
        for topic in REQUIRED:
            source=path/'review-sources'/(topic+'.json')
            source.write_text(json.dumps({'topic':topic,'synthetic_fixture':True,
                'case_context':branch['context']})+'\n')
            records[topic]={'topic':topic,'path':str(source.relative_to(path)),
                'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
                'reviewer':'synthetic-test',
                'observation':'Synthetic '+branch['context']+' source shape only'}
        context['independent_review']={'format':'c263073-source-review-v1','records':records,
            'case_context':branch['context'],
            'exception_dispositions':{name:{'status':'applies' if name == branch['target_exception'] else 'does_not_apply',
                'source_topics':sorted(EXCEPTION_TOPICS[name]),
                'reason':'Synthetic branch source shape only; legal verdict unresolved'} for name in EXCEPTIONS}}
    (path/'school-context.json').write_text(json.dumps(context)+'\n')
    with (path/'native-motion.jsonl').open('w') as motion,(path/'video_frames.jsonl').open('w') as frames,(path/'trace.jsonl').open('w') as trace:
        for index in range(600):
            native=index+100;x,y,heading=planned_pose(index,turn)
            body=[[x-1,y-1],[x+1,y-1],[x+1,y+1],[x-1,y+1]]
            motion.write(json.dumps({'frame':native,'native_frame':native,'video_frame':index,'time_s':index/20,
                'ego':{'center_xy_m':[x,y],'heading_deg':heading,'body_xy_m':body},
                'other_person':{'center_xy_m':[4,7.5]} if branch['child_actor'] else None,
                'control':{'steer':0.0,'throttle':0.0,'brake':0.0},
                'kinematic_path_only':False})+'\n')
            frames.write(json.dumps({'carla_frame':native,'native_frame':native,'video_frame':index,'time_s':index/20,
                'camera_native_frames':{name:native for name in CAMERAS}})+'\n')
            trace.write(json.dumps({'frame':native,'time_s':index/20,'position_m':[x,y,1],
                'heading_deg':heading})+'\n')
    for name in CAMERAS:(path/(name+'.mkv')).write_bytes(b'synthetic-diagnostic-not-video')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary);straight=root/'straight';turn=root/'turn';unreviewed=root/'unreviewed'
        fixture(straight,False);fixture(turn,True);fixture(unreviewed,True,False)
        a,b=measure(straight),measure(turn)
        assert a['cumulative_absolute_heading_change_deg']==0
        assert abs(b['cumulative_absolute_heading_change_deg']-180)<1e-6
        assert b['other_person_zone_frame_count']==600 and b['u_turn_legal_verdict']=='unresolved'
        straight_report=finalize_run(straight,straight/'analysis-report.json')
        turn_report=finalize_run(turn,turn/'analysis-report.json')
        assert straight_report['measurements']['school_zone_turn_observation']['value']['cumulative_absolute_heading_change_deg']==0
        assert abs(turn_report['measurements']['school_zone_turn_observation']['value']['cumulative_absolute_heading_change_deg']-180)<1e-6
        assert json.loads((turn/'result.json').read_text())['case_id'].endswith('__controlled_2')
        try:measure(unreviewed)
        except ValueError as error:assert 'Independent school-zone source review missing' in str(error)
        else:raise AssertionError('Unreviewed school zone accepted')
        (turn/'driver_reference.mkv').unlink()
        try:measure(turn)
        except ValueError as error:assert 'Missing required source' in str(error)
        else:raise AssertionError('Missing original camera accepted')
        print(json.dumps({'synthetic_saved_shape_passed':True,
            'straight_heading_change_deg':0,'turn_heading_change_deg':180,
            'person_zone_frames':600,'unreviewed_zone_rejected':True,
            'missing_camera_rejected':True,'saved_finalizers_passed':2,
            'u_turn_legal_verdict':'unresolved',
            'physical_acceptance_claimed':False}))


if __name__=='__main__':main()
