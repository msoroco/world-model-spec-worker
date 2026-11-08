"""Process source-bound saved entry, circulating, and exit phase observations."""
import hashlib
import json
import math
from pathlib import Path

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path): return [json.loads(line) for line in Path(path).read_text().splitlines()]

def measure(bundle,saved_dir=None):
    bundle=Path(bundle)
    config=json.loads((bundle/'connected-config.json').read_text())
    track=bundle/'connected-requested-tracks.jsonl'
    road=bundle/'connected-road.xodr'
    saved=Path(saved_dir) if saved_dir is not None else bundle/'connected-saved'
    observed_path=saved/'native-observed.jsonl'
    camera_path=saved/'camera-frames.jsonl'
    readback=json.loads((saved/'lane-readback.json').read_text())
    if (config['tracks_sha256']!=sha(track) or config['road_sha256']!=sha(road) or
        readback.get('road_sha256')!=sha(road) or
        readback.get('request_sha256')!=sha(track) or
        readback.get('source_kind') not in ('synthetic_cpu','original_native') or
        readback.get('physical_roundabout_verified') is not False):
        raise ValueError('C131364 saved connected provenance differs')
    if readback['source_kind']=='original_native' and (not readback.get('native_map_sha256') or
        readback.get('review_provenance')!='human_frame_review'):
        raise ValueError('C131364 original connected readback lacks review')
    requests=rows(track);observed=rows(observed_path);camera=rows(camera_path)
    if len(requests)!=240 or len(observed)!=240 or len(camera)!=240:
        raise ValueError('C131364 connected saved frame count differs')
    phase_counts={'entry':0,'circulation':0,'exit':0}
    body_contained=0;visible=0;previous=None;previous_phase=-1
    entry_headings=[];exit_headings=[]
    original=readback['source_kind']=='original_native'
    first_native=observed[0].get('native_frame')
    if original and (type(first_native) is not int or not readback.get('ego_actor_id')):
        raise ValueError('C131364 original actor identity absent')
    for i,(request,row,frame) in enumerate(zip(requests,observed,camera)):
        if (request.get('frame')!=i or row.get('frame')!=i or frame.get('frame')!=i or
            row.get('native_frame')!=frame.get('camera_frame') or
            row.get('time_s')!=request.get('time_s') or frame.get('time_s')!=row.get('time_s') or
            row.get('source_kind')!=readback['source_kind'] or frame.get('source_kind')!=readback['source_kind'] or
            row.get('witness')!=request.get('witness') or row.get('candidate_id')!=request.get('candidate_id') or
            row.get('lane_id')!=config['requested_lane_id'] or
            type(frame.get('left_lane_visible')) is not bool):
            raise ValueError(f'C131364 connected saved join differs at {i}')
        if original:
            if (row.get('native_frame')!=first_native+i or
                row.get('ego_actor_id')!=readback['ego_actor_id'] or
                row.get('ego_blueprint')!='vehicle.tesla.model3' or
                row.get('phase')!={10:'entry',11:'circulation',12:'exit'}.get(row.get('road_id')) or
                row.get('actual_exit_observed')!=(row.get('road_id')==12) or
                not all(type(row.get(k)) in (int,float) and math.isfinite(row[k])
                    for k in ('ego_x_m','ego_y_m','ego_speed_mps','ego_heading_deg')) or
                row['ego_speed_mps']<0):
                raise ValueError('C131364 original road, actor or pose differs')
        elif (row.get('phase')!=request.get('phase') or
              row.get('road_id')!=request.get('road_id') or
              row.get('actual_exit_observed') is not False):
            raise ValueError('C131364 synthetic saved route differs')
        x,y=row['ego_x_m'],row['ego_y_m']
        if not original and (abs(x-request['ego_x_m'])>.01 or abs(y-request['ego_y_m'])>.01):
            raise ValueError('C131364 connected saved route differs')
        body=row.get('ego_body_xy_m')
        if (not isinstance(body,list) or len(body)<4 or any(
            not isinstance(point,list) or len(point)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in point)
            for point in body)):
            raise ValueError('C131364 connected saved body absent')
        if previous is not None:
            measured_speed=20*math.hypot(x-previous[0],y-previous[1])
            if abs(measured_speed-row['ego_speed_mps'])>.5:
                raise ValueError('C131364 connected saved speed differs')
        previous=(x,y)
        phase=row['phase'];phase_counts[phase]+=1
        phase_number={'entry':0,'circulation':1,'exit':2}[phase]
        if original and phase_number<previous_phase:
            raise ValueError('C131364 original route reverses phase')
        previous_phase=phase_number
        if original and phase=='entry':entry_headings.append(row['ego_heading_deg'])
        if original and phase=='exit':exit_headings.append(row['ego_heading_deg'])
        if phase=='circulation':
            lower,upper=(22,25.5) if row['lane_id']==-1 else (25.5,29)
            if all(lower<=math.hypot(*point)<=upper for point in body):body_contained+=1
        if frame['left_lane_visible']:visible+=1
    if config['candidate_id']=='fallback3':
        if phase_counts['circulation'] or phase_counts['exit']:raise ValueError('C131364 stop fallback passed entry')
    elif not all(phase_counts.values()):
        raise ValueError('C131364 connected saved route lacks exit phase')
    if original and phase_counts['exit'] and body_contained!=phase_counts['circulation']:
        raise ValueError('C131364 original circulating body leaves requested lane')
    if original and phase_counts['exit']:
        entry_heading=math.radians(entry_headings[0])
        exit_heading=math.radians(exit_headings[-1])
        heading_change=math.atan2(math.sin(exit_heading-entry_heading),
                                  math.cos(exit_heading-entry_heading))
        if not math.radians(60)<=heading_change<=math.radians(120):
            raise ValueError('C131364 original left-exit heading differs')
    return {'format':'c131364-connected-saved-measurement-v1',
            'case_id':config['case_id'],'candidate_id':config['candidate_id'],
            'source_kind':readback['source_kind'],
            'source_hashes':{'request':sha(track),'road':sha(road),
                             'observed':sha(observed_path),'camera':sha(camera_path)},
            'phase_frames':phase_counts,'full_body_circulation_lane_frames':body_contained,
            'left_lane_visible_frames':visible,
            'actual_left_exit_observed':original and phase_counts['exit']>0,
            'observed_entry_to_exit_heading_change_deg':
                round(math.degrees(heading_change),3) if original and phase_counts['exit'] else None,
            'physical_roundabout_verified':False,'legal_verdict':None,'delivery_ready':False}

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path)
    parser.add_argument('--saved-dir',type=Path)
    args=parser.parse_args();print(json.dumps(measure(args.bundle,args.saved_dir)))
