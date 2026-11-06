"""Unselected C10316 engineering alternatives with original-source trigger rules."""
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent.parent
BASE='training__C10316__NRS-484B-293__pedestrian'


def candidate(case_suffix,candidate_id):
    if case_suffix not in ('reference','contrast'):
        raise ValueError('Unknown crosswalk comparison case')
    side=-.65 if case_suffix=='reference' else .65
    plans={
        'primary':{'spawn_start_x_m':-4.0,'capture_start_x_m':-4.0,
                   'pre_roll_s':0.0,'target_lateral_m':side,
                   'controller_lookahead_s':.5,'camera_overhead_z_m':6.0,
                   'trigger':{'kind':'initial','source':'none','threshold':None}},
        'fallback1':{'spawn_start_x_m':-6.0,'capture_start_x_m':-4.0,
                     'pre_roll_s':3.0,'target_lateral_m':side,
                     'controller_lookahead_s':.5,'camera_overhead_z_m':6.0,
                     'trigger':{'kind':'native_spawn_clearance_m_below',
                                'source':'original_native_actor_and_crosswalk_geometry',
                                'threshold':1.0}},
        'fallback2':{'spawn_start_x_m':-4.0,'capture_start_x_m':-4.0,
                     'pre_roll_s':0.0,'target_lateral_m':side,
                     'controller_lookahead_s':.25,'camera_overhead_z_m':6.0,
                     'trigger':{'kind':'native_path_tracking_error_m_above',
                                'source':'original_native_pedestrian_pose_and_requested_path',
                                'threshold':.2,'minimum_frames':10}},
        'fallback3':{'spawn_start_x_m':-4.0,'capture_start_x_m':-4.0,
                     'pre_roll_s':0.0,'target_lateral_m':side,
                     'controller_lookahead_s':.5,'camera_overhead_z_m':9.0,
                     'trigger':{'kind':'independent_original_pixel_visibility_below',
                                'source':'four_synchronized_original_camera_streams',
                                'threshold':.95}}
    }
    if candidate_id not in plans:
        raise ValueError('Unknown crosswalk candidate')
    return {'case_id':BASE+'__'+case_suffix,'candidate_id':candidate_id,
            'law_id':'NRS-484B-293','cell_id':'C10316','actor':'pedestrian',
            'comparison_variable':'pedestrian_lateral_crosswalk_half',
            'duration_s':12,'rate_hz':20,'road_source':'native/road.xodr',
            'crosswalk_id':'C10316-authored-alley-crosswalk',
            'engineering':plans[candidate_id],
            'scope':'unselected authored engineering proposal; trigger not physically measured'}


def check():
    manifest=[]
    for suffix in ('reference','contrast'):
        plans=[candidate(suffix,key) for key in ('primary','fallback1','fallback2','fallback3')]
        assert len({json.dumps(p['engineering'],sort_keys=True) for p in plans})==4
        assert len({p['case_id'] for p in plans})==1
        assert len({(p['law_id'],p['cell_id'],p['actor'],p['duration_s'],p['rate_hz'],p['crosswalk_id']) for p in plans})==1
        assert len({p['engineering']['target_lateral_m'] for p in plans})==1
        assert all(p['engineering']['trigger']['source']!='none' for p in plans[1:])
        for plan in plans:
            out=HERE/'draft-candidates'/suffix/plan['candidate_id']/'construction.json'
            out.parent.mkdir(parents=True,exist_ok=True)
            out.write_text(json.dumps(plan,indent=2)+'\n')
            manifest.append(str(out.relative_to(HERE)))
    assert candidate('reference','primary')['engineering']['target_lateral_m']==-.65
    assert candidate('contrast','primary')['engineering']['target_lateral_m']==.65
    return {'unselected_candidate_drafts':len(manifest),'paths':manifest,
            'physical_triggers_measured':0,'selected_cases':0}


if __name__=='__main__':
    print(json.dumps(check(),sort_keys=True))
