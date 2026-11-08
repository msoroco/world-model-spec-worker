"""Four distinct rider-yield Native construction policies and measured triggers."""
import hashlib
import json
from pathlib import Path
from measure_facility import overlap_area
from rider_engineering import CONFLICT_BOUNDS_M, RELEASE_FRAME, ego_pose

NAMES=('primary','fallback1','fallback2','fallback3')
RIDER_TYPES=('bicycle','electric_bicycle','electric_scooter')


def parameters(rider_type,response,candidate):
    if rider_type not in RIDER_TYPES or response not in RELEASE_FRAME or candidate not in NAMES:
        raise ValueError('Unknown exact rider case or candidate')
    return {'rider_type':rider_type,'response':response,'candidate':candidate,
            'approach_start_x_m':-55.0 if candidate=='fallback1' else -45.0,
            'release_shift_frames':5 if candidate=='fallback2' else 0,
            'reference_camera_xyz_m':[8.0,-10.0,14.0] if candidate=='fallback3' else [10.0,-8.0,10.0],
            'ego_speed_mps':8.0,'rider_speed_mps':4.0,
            'rider_y_m':-4.0,'conflict_bounds_m':[-2.5,-5.0,2.5,-3.0]}


def trigger_values(approach_start_x_m,first_ego_frame,expected_ego_frame,
                   visible_conflict_frames,total_conflict_frames):
    if type(approach_start_x_m) not in (int,float) or not -60<=approach_start_x_m<=-35:
        raise ValueError('Invalid measured start')
    if type(first_ego_frame) is not int or type(expected_ego_frame) is not int:
        raise ValueError('Invalid measured conflict entry frame')
    if type(visible_conflict_frames) is not int or type(total_conflict_frames) is not int or not 0<=visible_conflict_frames<=total_conflict_frames or total_conflict_frames==0:
        raise ValueError('Invalid measured visibility count')
    runway_m=-9.0-approach_start_x_m
    error_frames=abs(first_ego_frame-expected_ego_frame)
    visibility=visible_conflict_frames/total_conflict_frames
    return {'approach_runway_m':runway_m,'ego_entry_error_frames':error_frames,
            'body_visible_fraction':round(visibility,6),
            'fallback1_trigger_measured':runway_m<35.0,
            'fallback2_trigger_measured':error_frames>5,
            'fallback3_trigger_measured':visibility<.95}


def evaluate_sources(folder):
    folder=Path(folder)
    manifest=json.loads((folder/'rider-trigger-sources.json').read_text())
    if manifest.get('source_kind')!='synthetic_cpu_fixture' or manifest.get('accepted') is not False:
        raise ValueError('Invalid trigger source scope')
    for name,digest in manifest['sha256'].items():
        path=folder/name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
            raise ValueError('Rider trigger source hash differs: '+name)
    samples=[json.loads(line) for line in (folder/'native_rider_ego_samples.jsonl').read_text().splitlines()]
    visibility=[json.loads(line) for line in (folder/'camera_visibility.jsonl').read_text().splitlines()]
    if len(samples)!=480 or len(visibility)!=480:
        raise ValueError('Missing trigger frames')
    if any((a['native_frame'],a['time_s'])!=(b['native_frame'],b['time_s'])
           for a,b in zip(samples,visibility)):
        raise ValueError('Trigger frame/time join failed')
    ego=[i for i,row in enumerate(samples)
         if overlap_area(row['ego_body_xy'],CONFLICT_BOUNDS_M)>.01]
    rider=[i for i,row in enumerate(samples)
           if overlap_area(row['rider_body_xy'],CONFLICT_BOUNDS_M)>.01]
    if not ego or not rider:
        raise ValueError('Missing source-bound conflict observation')
    start_x=sum(p[0] for p in samples[0]['ego_body_xy'])/4
    visible=sum(visibility[i]['rider_and_ego_body_visible'] is True for i in rider)
    values=trigger_values(start_x,samples[ego[0]]['native_frame'],
                          manifest['expected_ego_frame'],visible,len(rider))
    return {'case_id':manifest['case_id'],'fixture':manifest['fixture'],
            'first_ego_frame':samples[ego[0]]['native_frame'],
            'last_rider_frame':samples[rider[-1]]['native_frame'],
            'rider_conflict_frames':len(rider), 'visible_conflict_frames':visible,
            **values}


def check():
    base=parameters('bicycle','clear','primary')
    changed=[]
    for candidate in NAMES[1:]:
        variant=parameters('bicycle','clear',candidate)
        different={key for key in ('approach_start_x_m','release_shift_frames','reference_camera_xyz_m')
                   if variant[key]!=base[key]}
        changed.append(different)
    assert changed==[{'approach_start_x_m'},{'release_shift_frames'},
                     {'reference_camera_xyz_m'}]
    assert ego_pose(0,'clear',-55.0)['center_xy']==[-55.0,-1.5]
    assert ego_pose(479,'clear',-55.0)['road_id']==2
    assert ego_pose(479,'clear',-45.0,5)['road_id']==2
    return {'cases':6,'candidates_per_case':4,'distinct_knob_sets':[sorted(x) for x in changed],
            'original_native_actor_verified':False,'camera_visibility_verified':False}


if __name__=='__main__':
    import json
    print(json.dumps(check(),indent=2))
