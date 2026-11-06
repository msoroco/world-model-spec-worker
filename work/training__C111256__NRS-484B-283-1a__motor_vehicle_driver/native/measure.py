"""Source-hashed uncontrolled crosswalk, directional half and cited exception measurements."""
from __future__ import annotations
import hashlib,json,math
from pathlib import Path
RATE_HZ=20
FRAMES=480
CROSSWALK_Y=(-12.0,-10.0)
BODY_HALF_LENGTH=2.6

def sha256(path:Path)->str:return hashlib.sha256(path.read_bytes()).hexdigest()

def measure(path:Path,expected_sha256:str)->dict:
    if sha256(path)!=expected_sha256:raise ValueError('Source bytes differ')
    record=json.loads(path.read_text())
    if record.get('source_kind') not in ('synthetic_cpu','original_native_and_video'):
        raise ValueError('Unsupported source kind')
    frames=record.get('frames')
    if not isinstance(frames,list) or len(frames)!=FRAMES:raise ValueError('Requires exactly 480 frames')
    case=record.get('case')
    if case not in ('witness_1','witness_2','exception_1_1','exception_1_2'):
        raise ValueError('Unknown exact case')
    prior=None;prior_speed=None;first_overlap=None;last_ped=None;conflict_overlap=[];halt=[]
    for i,row in enumerate(frames):
        if row.get('frame')!=i or row.get('video_frame')!=i or row.get('native_frame')!=i:
            raise ValueError('Original frame join differs')
        if abs(row.get('time_s',-100)-i/RATE_HZ)>1e-8:raise ValueError('Frame timestamp differs')
        if row.get('official_device_actors_present') is not False:
            raise ValueError('Uncontrolled-crosswalk device absence source missing')
        if row.get('crosswalk_marked') is not True or row.get('pedestrian_on_ego_highway_half') is not True:
            raise ValueError('Marked crosswalk or ego highway-half source missing')
        if row.get('road_one_way') is not False or row.get('ego_directional_lanes')!=[-1]:
            raise ValueError('Directional highway-half definition differs')
        if row.get('white_cane_declared') is not (case=='exception_1_2') or row.get('pedestrian_blind_declared') is not (case=='exception_1_2'):
            raise ValueError('Cited blind-white-cane exception source differs')
        y=row.get('ego_y_m');x=row.get('ego_x_m');speed=row.get('ego_speed_m_s')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in (x,y,speed)) or speed<0:
            raise ValueError('Measured ego pose or speed absent')
        if prior is not None and math.dist((x,y),prior)>max(speed,prior_speed)/RATE_HZ+.02:
            raise ValueError('Pose step exceeds speed')
        prior=(x,y);prior_speed=speed
        front=y+BODY_HALF_LENGTH;rear=y-BODY_HALF_LENGTH
        overlap=front>=CROSSWALK_Y[0] and rear<=CROSSWALK_Y[1]
        if overlap and first_overlap is None:first_overlap=i
        if speed<=.05 and front<CROSSWALK_Y[0]:halt.append(i)
        if row.get('pedestrian_conflict_occupied') is True:
            last_ped=i
            if overlap:conflict_overlap.append(i)
    if first_overlap is None or last_ped is None:raise ValueError('Crosswalk or pedestrian observation absent')
    before=[i for i in halt if i<first_overlap]
    longest=0;run=0;previous=-2
    for i in before:
        run=run+1 if i==previous+1 else 1;longest=max(longest,run);previous=i
    yielded=not conflict_overlap
    return {'source_sha256':expected_sha256,'source_kind':record['source_kind'],'case':case,
            'frames':FRAMES,'rate_hz':RATE_HZ,'official_devices_absent_in_source':True,
            'marked_crosswalk_and_ego_directional_half_in_source':True,
            'first_ego_crosswalk_overlap_frame':first_overlap,
            'last_pedestrian_ego_half_conflict_frame':last_ped,
            'ego_pedestrian_overlap_frames':conflict_overlap,
            'yielded_to_crosswalk_pedestrian':yielded,
            'pre_crosswalk_stationary_frames_contiguous':longest,
            'full_halt_before_crosswalk':longest>=10,
            'blind_white_cane_exception_declared':case=='exception_1_2',
            'blind_white_cane_physically_verified':False,
            'legal_verdict':None,
            'physical_behavior_observed':record['source_kind']=='original_native_and_video'}

def synthetic(case:str)->dict:
    if case not in ('witness_1','witness_2','exception_1_1','exception_1_2'):
        raise ValueError('Unknown exact case')
    release=130 if case=='witness_2' else 170
    rows=[]
    for f in range(FRAMES):
        if f<100:y=-40+23*f/99;speed=23/99*RATE_HZ
        elif f<release:y=-17.0;speed=0.0
        elif f<release+40:y=-17+15*(f-release)/40;speed=7.5
        else:y=-2+(f-release-40)*.15;speed=3.0
        rows.append({'frame':f,'video_frame':f,'native_frame':f,'time_s':f/RATE_HZ,
            'ego_x_m':1.75,'ego_y_m':round(y,6),'ego_speed_m_s':speed,
            'official_device_actors_present':False,'crosswalk_marked':True,
            'pedestrian_on_ego_highway_half':True,'road_one_way':False,
            'ego_directional_lanes':[-1],
            'pedestrian_conflict_occupied':140<=f<=160,
            'pedestrian_blind_declared':case=='exception_1_2',
            'white_cane_declared':case=='exception_1_2',
            'white_cane_visual_prop_physically_verified':False})
    return {'source_kind':'synthetic_cpu','case':case,'law_id':'NRS-484B-283-1a',
            'cell_id':'C111256','scope':'synthetic CPU saved-path test only; no Native or original pixels',
            'frames':rows}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    for case in ('witness_1','witness_2','exception_1_1','exception_1_2'):
        path=args.output/(case+'-480.json');path.write_text(json.dumps(synthetic(case),separators=(',',':'))+'\n')
        print(json.dumps(measure(path,sha256(path))))
