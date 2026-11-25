"""Saved-only, source-hashed rotary motion measurement; no legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

REQUIRED=('native-raw-actors.jsonl','native-map-readback.json','video_frames.jsonl',
          'trace.jsonl','capture/evidence.jsonl','capture/manifest.json')
CAMERAS=('overview','approach','reference_corner','driver_reference')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    if not Path(path).is_file():raise ValueError('Missing required source: '+str(path))
    return json.loads(Path(path).read_text())
def lines(path):
    if not Path(path).is_file():raise ValueError('Missing required source: '+str(path))
    return [json.loads(x) for x in Path(path).read_text().splitlines()]
def finite(x):return type(x) in (float,int) and math.isfinite(x)

def count_video(path):
    if not path.is_file():raise ValueError('Missing required source: '+path.name)
    proc=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
       '-show_entries','stream=nb_read_frames','-of','default=noprint_wrappers=1:nokey=1',str(path)],
       capture_output=True,text=True,timeout=120)
    if proc.returncode or not proc.stdout.strip().isdigit():
        raise ValueError('Source camera video did not decode: '+path.name)
    return int(proc.stdout.strip())

def measure(attempt):
    attempt=Path(attempt)
    cfg=read(attempt/'config.json');observed=lines(attempt/'native-raw-actors.jsonl')
    mapping=lines(attempt/'video_frames.jsonl');trace=lines(attempt/'trace.jsonl')
    evidence=lines(attempt/'capture/evidence.jsonl');manifest=read(attempt/'capture/manifest.json')
    native_map=read(attempt/'native-map-readback.json')
    if not all(len(x)==600 for x in (observed,mapping,trace,evidence)) or manifest.get('frames')!=600:
        raise ValueError('Original 600-frame source coverage differs')
    source={name:sha(attempt/name) for name in REQUIRED}
    if native_map.get('road_sha256')!=cfg.get('road_sha256') or not native_map.get('native_map_sha256'):
        raise ValueError('Original Native map source differs')
    if set(native_map.get('arc_lane_readback',{}))!={'-1','-2'}:
        raise ValueError('Native rotary lanes not read back')
    first=mapping[0]['native_frame'];last_time=-math.inf
    angles=[];headings=[];body_clear=[];lanes=[];speed=[];time=[]
    for i,(n,m,t,e) in enumerate(zip(observed,mapping,trace,evidence)):
        f=m.get('native_frame');s=m.get('time_s');ego=n.get('ego',{})
        if (m.get('video_frame')!=i or type(f) is not int or f!=first+i or
            n.get('frame')!=i or n.get('native_frame')!=f or
            t.get('frame')!=f or e.get('original_frame')!=f or
            not finite(s) or s<=last_time or not finite(n.get('time_s')) or
            abs(n['time_s']-s)>1e-4 or abs(t['time_s']-s)>1e-4 or
            abs(e['recording_time_s']-s)>1e-4):
            raise ValueError('Original Native frame/time join differs')
        last_time=s;time.append(s)
        xyz=ego.get('center_native_xyz_m');body=ego.get('body_native_xyz_m')
        if not isinstance(xyz,list) or len(xyz)!=3 or not all(finite(v) for v in xyz):
            raise ValueError('Original Native ego position absent')
        if not isinstance(body,list) or len(body)!=8 or any(len(p)!=3 or
                not all(finite(v) for v in p) for p in body):
            raise ValueError('Original Native body vertices absent')
        if ego.get('blueprint')!='vehicle.tesla.model3' or not ego.get('actor_id'):
            raise ValueError('Original Native ego identity differs')
        if not finite(ego.get('yaw_deg')) or not finite(ego.get('speed_mps')):
            raise ValueError('Original Native motion absent')
        angles.append(math.atan2(xyz[1],xyz[0]));headings.append(math.radians(ego['yaw_deg']))
        body_clear.append(min(math.hypot(p[0],p[1])-15 for p in body))
        lanes.append(n.get('observed_lane_id'));speed.append(ego['speed_mps'])
    steps=[math.atan2(math.sin(b-a),math.cos(b-a)) for a,b in zip(angles,angles[1:])]
    yaws=[math.atan2(math.sin(b-a),math.cos(b-a)) for a,b in zip(headings,headings[1:])]
    sign=cfg['requested_rotation_sign'];signed=sum(steps)
    lane_occupancy=sum(lane in (-1,-2) for lane in lanes)
    matched=(len(steps)==599 and all(step*sign>0 for step in steps) and
             all(yaw*sign>0 for yaw in yaws) and lane_occupancy==600 and
             min(body_clear)>0)
    return {'value':{'signed_angular_progress_rad':round(signed,6),
              'minimum_signed_step_rad':round(min(step*sign for step in steps),8),
              'minimum_signed_yaw_step_rad':round(min(yaw*sign for yaw in yaws),8),
              'rotary_lane_samples':lane_occupancy,'minimum_body_island_clearance_m':round(min(body_clear),4),
              'maximum_speed_mps':round(max(speed),4),'direction_request_matched':matched,
              'physical_roundabout_design_verified':False},
            'method':'measure',
            'measurement_description':'original Native body centers, heading, lane IDs and island polygon over 600 joined frames',
            'sources':source,'time_window_s':[time[0],time[-1]],'frame_window':[first,first+599]}

def finalise(attempt,output):
    attempt=Path(attempt).resolve();output=Path(output).resolve()
    if output.exists() or (attempt/'result.json').exists():
        raise ValueError('Retain prior analysis; choose fresh saved attempt')
    cfg=read(attempt/'config.json');measurement=measure(attempt)
    videos=[f'{name}.mkv' for name in CAMERAS]
    video_counts={name:count_video(attempt/name) for name in videos}
    if any(count!=600 for count in video_counts.values()):
        raise ValueError('Four original camera videos lack 600 frames')
    description=cfg['recording_description'];channel_dir=attempt/'channels'
    channel_dir.mkdir(exist_ok=True)
    rows=lines(attempt/'native-raw-actors.jsonl');mapping=lines(attempt/'video_frames.jsonl')
    previous_yaw=None
    for channel in description['channels']:
        name=channel['name'];path=channel_dir/(name+'.jsonl')
        if path.exists():raise ValueError('Derived channel already exists: '+name)
        out=[]
        for index,(row,frame) in enumerate(zip(rows,mapping)):
            ego=row['ego'];xyz=ego['center_native_xyz_m']
            if name=='st.roundabout':value=read(attempt/'native-map-readback.json')
            elif name=='rel.occupies':value={'body_native_xyz_m':ego['body_native_xyz_m'],'lane_id':row['observed_lane_id']}
            elif name=='kin.heading':value=ego['yaw_deg']
            elif name=='kin.position':value=xyz
            elif name=='kin.yaw_rate':
                current=math.radians(ego['yaw_deg'])
                if previous_yaw is None:
                    following=math.radians(rows[1]['ego']['yaw_deg'])
                    value=math.atan2(math.sin(following-current),
                                     math.cos(following-current))*20
                else:
                    value=math.atan2(math.sin(current-previous_yaw),
                                     math.cos(current-previous_yaw))*20
                previous_yaw=current
            elif name=='drv.wrong_way':value={'signed_rotation_request':cfg['requested_rotation_sign'],
                                              'observed_signed_progress_rad':measurement['value']['signed_angular_progress_rad']}
            elif name=='native_body_pose_control':value=ego
            elif name=='camera_frame_join':value=frame
            else:raise ValueError('Unknown derived rotary channel: '+name)
            out.append(json.dumps({'time_s':frame['time_s'],'value':value},allow_nan=False))
        path.write_text('\n'.join(out)+'\n')
    from worker_exchange.native_output import validate_result
    sources=measurement['sources'];recording_evidence=[{'name':c['name'],'unit':c['unit'],
       'reference':'channels/'+c['name']+'.jsonl'} for c in description['channels']]
    recording_evidence.append({'name':'rotary_island_source','unit':'structured',
                               'reference':'context.json'})
    result={'case_id':cfg['case_id'],'measured_values':measurement['value'],
      'target_checks':[{'target':'continuous signed original Native circulation engineering target',
          'requested':cfg['requested_rotation_sign'],'measured':measurement['value']['signed_angular_progress_rad'],
          'method':measurement['measurement_description'],'tolerance':'same sign at all 599 sampled intervals; body within authored ring',
          'matched':measurement['value']['direction_request_matched'],
          'physical_cause_confirmed':False,'cause_evidence':sources}],
      'setup_confirmed':False,'behavior_attempted':True,
      'maneuver_completed':measurement['value']['direction_request_matched'],
      'termination_reason':'full 600-frame original Native source analyzed; physical/legal review pending',
      'physical_failure_flags':['roundabout_design_and_pixels_not_reviewed'],
      'trace_reference':'trace.jsonl','video_references':videos,
      'video_frame_map_reference':'video_frames.jsonl','recording_description':description,
      'recording_evidence':recording_evidence,
      'realized_observables':{'sampled_signed_angular_progress_rad':{
          'value':measurement['value']['signed_angular_progress_rad'],'unit':'rad','statistic':'sum of 599 wrapped angle steps',
          'method':measurement['measurement_description'],'time_window':'original full 30 s','reference':'native-raw-actors.jsonl'}},
      'provenance_kind':'native' if (attempt/'capture-seal.json').is_file() else 'synthetic_local_diagnostic',
      'accepted':False,'legal_verdict_claimed':False}
    validate_result(result)
    report={'format':'c234827-rotary-saved-v1','case_id':cfg['case_id'],
       'candidate_id':cfg.get('candidate_id','primary'),
       'measurements':{'rotation_observation':measurement},
       'video_frames':video_counts,'source_kind':result['provenance_kind'],
       'scope':'saved original sources; CPU fixture is diagnostic; no legal verdict or physical acceptance'}
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    (attempt/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True);args=parser.parse_args()
    print(json.dumps(finalise(args.attempt,args.output),allow_nan=False))
if __name__=='__main__':main()
