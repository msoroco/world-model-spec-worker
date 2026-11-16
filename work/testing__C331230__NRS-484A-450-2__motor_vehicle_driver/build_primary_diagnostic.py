"""Synthetic four-frame source diagnostic for the marked-crosswalk finalizer."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent

def write(path,value):path.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def jsonl(path,rows):path.write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))

def build(output):
 output=Path(output)
 if output.exists():raise ValueError('Retain prior diagnostic; choose a fresh output')
 output.mkdir(parents=True);(output/'capture').mkdir()
 for name in ('config.json','site.json'):shutil.copyfile(HERE/name,output/name)
 site=json.loads((output/'site.json').read_text())
 ctx={'native_map_id':site['native_map_name'],'intersection_id':44,
  'approach_road_id':1,'approach_lane_id':-1,'native_stop_sign_id':17,
  'sign_governance_source':'synthetic Native-shaped sign ID; authority unreviewed',
  'crosswalk_source':'synthetic marked near-side polygon',
  'crosswalk_nearside_source':'synthetic CPU geometry',
  'junction_source':'synthetic CPU geometry','near_side_crosswalk_exists':True,
  'crosswalk_origin':'marked','crosswalk_polygon_xy_m':site['crosswalk_polygon_xy_m'],
  'intersection_polygon_xy_m':site['intersection_polygon_xy_m'],
  'approach_forward_xy':[1,0],'stop_line_exists':False,
  'physical_acceptance_claimed':False,'legal_conclusion':'unresolved'}
 write(output/'approach_context.json',ctx)
 hist=[];frames=[];trace=[];evidence=[]
 for i,(x,speed) in enumerate([(0,0),(4,2),(7,2),(12,2)]):
  frame=100+i;time=round(1+i*.05,8)
  body=[[x-1,-1],[x-1,1],[x+1,1],[x+1,-1]]
  hist.append({'frame':frame,'time_s':time,'road_id':1,'lane_id':-1,
       'stop_sign_id':17,'ego_speed_mps':speed,'ego_body_vertices_xy_m':body})
  frames.append({'video_frame':i,'carla_frame':frame,'time_s':time})
  trace.append({'frame':frame,'time_s':time,'position':{'x':x,'y':0,'z':0},
       'position_m':[x,0,0],'heading_deg':0,'speed_mps':speed})
  evidence.append({'original_frame':frame,'recording_time_s':time,
       'actor_id':101,'ego':{'body_vertices_xy_m':body,'speed_mps':speed},
       'supporting_only':True})
 jsonl(output/'stop_history.jsonl',hist);jsonl(output/'video_frames.jsonl',frames)
 jsonl(output/'trace.jsonl',trace);jsonl(output/'capture/evidence.jsonl',evidence)
 for name,dimensions in [('overview',(1920,1080)),('approach',(1280,720)),
                         ('reference_corner',(1280,720)),('driver_reference',(1280,720))]:
  command=['ffmpeg','-hide_banner','-loglevel','error','-f','lavfi','-i',
    f'color=c=black:s={dimensions[0]}x{dimensions[1]}:r=20:d=0.2',
    '-frames:v','4','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p',
    '-y',str(output/(name+'.mkv'))]
  subprocess.run(command,check=True)
 print(json.dumps({'case_id':json.loads((output/'config.json').read_text())['selected_case_id'],
       'diagnostic_fixture':True,'frames':4,'physical_acceptance_claimed':False}))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path)
 build(p.parse_args().output)
