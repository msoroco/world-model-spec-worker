"""Independent saved-evidence delivery audit; never starts CARLA or judges legality."""
import argparse,hashlib,json,math,subprocess,sys
from pathlib import Path
VIEWS=('overview','approach','reference_corner','driver_reference')
CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path):return json.loads(path.read_text())
def rows(path):
 if not path.is_file():raise ValueError('Missing original source: '+path.name)
 return [json.loads(s) for s in path.read_text().splitlines() if s]
def required(ok,message):
 if not ok:raise ValueError(message)
def video_info(path):
 p=subprocess.run(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames','-of','json',str(path)],capture_output=True,text=True)
 required(p.returncode==0,'Full video decode failed: '+path.name)
 stream=json.loads(p.stdout).get('streams',[])
 required(len(stream)==1 and int(stream[0].get('nb_read_frames') or 0)>0,'Full video decode failed: '+path.name)
 return stream[0]
def pixel_region(path,frame,box,info):
 x,y,w,h=box
 required(all(type(v) is int for v in box) and x>=0 and y>=0 and w>1 and h>1 and x+w<=info['width'] and y+h<=info['height'],'Pixel review region out of bounds')
 vf=f'select=eq(n\\,{frame}),crop={w}:{h}:{x}:{y}'
 p=subprocess.run(['ffmpeg','-v','error','-i',str(path),'-vf',vf,'-frames:v','1','-f','image2pipe','-vcodec','ppm','pipe:1'],capture_output=True)
 required(p.returncode==0 and p.stdout,'Relevant pixel frame unavailable')
 required(p.stdout.startswith(b'P6\n'),'Relevant pixel decoder returned unexpected format')
 values=p.stdout.split(b'\n',3)[3]
 required(len(values)==w*h*3,'Relevant pixel frame size differs')
 required(max(values)-min(values)>=8,'Relevant visible pixels lack image detail')
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--job',required=True);p.add_argument('--attempt',type=Path,required=True);p.add_argument('--recording',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--attempt-number',type=int);p.add_argument('--fixture-test',action='store_true')
 a=p.parse_args();root=a.attempt.resolve();required(root.is_dir(),'Attempt directory missing')
 result_path=root/'result.json';required(result_path.is_file(),'Missing original source: result.json');result=load(result_path)
 required(result.get('case_id')==a.case,'Native source case identity mismatch')
 provenance=load(root/'acquisition-provenance.json');required(provenance.get('provenance_kind')=='native' and (a.fixture_test or provenance.get('diagnostic_fixture') is not True),'Native source provenance required')
 config_path=root/'config.json';required(config_path.is_file(),'Missing original source: config.json');config=load(config_path)
 trace=rows(root/'trace.jsonl');mapping=rows(root/'video_frames.jsonl');evidence=rows(root/'capture/evidence.jsonl')
 required(len(trace)>1 and len(trace)==len(mapping)==len(evidence),'Original frame sequence incomplete')
 duration=config.get('duration_s');rate=config.get('rate_hz')
 required(isinstance(duration,(int,float)) and isinstance(rate,(int,float)) and duration>0 and rate>0,'Original capture duration contract missing')
 required(len(trace)>=round(duration*rate)-1 and trace[-1]['time_s']-trace[0]['time_s']>=duration-1/rate-1e-3,'Physical episode duration incomplete')
 ids=None
 for i,(t,m,e) in enumerate(zip(trace,mapping,evidence)):
  required(m.get('video_frame')==i and t.get('frame')==m.get('carla_frame')==e.get('frame'),'Original frame identity join failed')
  times=(t.get('time_s'),m.get('time_s'),e.get('time_s'))
  required(all(isinstance(v,(float,int)) and math.isfinite(v) for v in times) and max(times)-min(times)<1e-4,'Original timestamp join failed')
  if i:required(times[0]>trace[i-1]['time_s'],'Original timestamps are not increasing')
  people=e.get('participants')
  required(isinstance(people,list) and people,'Required participants missing')
  current={p.get('actor_id') for p in people if p.get('actor_id') is not None}
  required(len(current)==len(people),'Duplicate or unidentified participants')
  if ids is None:ids=current
  required(current==ids,'Required participant history incomplete')
 required(len(ids)>=1,'Required participants missing')
 core_path=root/'traffic_spec/trace.json';required(core_path.is_file(),'Missing Core trace: traffic_spec/trace.json');scenes=load(core_path).get('scenes')
 required(isinstance(scenes,list) and len(scenes)==len(mapping),'Core scene count differs from original frames')
 required(all(scene.get('t')==round(frame['time_s']*1000) for scene,frame in zip(scenes,mapping)),'Core timestamp join failed')
 videos={name:root/(name+'.mkv') for name in VIEWS};videos['raw']=root/'raw.mkv'
 info={}
 for name,path in videos.items():
  required(path.is_file(),'Missing original video: '+name)
  info[name]=video_info(path)
  required(int(info[name]['nb_read_frames'])==len(trace),'Full video decode frame count differs: '+name)
 review=load(root/'pixel-review.json')
 required(review.get('case_id')==a.case and isinstance(review.get('regions'),list) and review['regions'],'Relevant pixel review missing')
 for region in review['regions']:
  name=region.get('view');required(name in VIEWS,'Pixel review uses unknown source view')
  required(region.get('source_sha256')==sha(videos[name]),'Pixel review source hash changed')
  frame=region.get('frame');required(type(frame) is int and 0<=frame<len(trace),'Pixel review frame out of range')
  required(region.get('subject') and region.get('visible') is True,'Relevant subject not visibly reviewed')
  pixel_region(videos[name],frame,region.get('box'),info[name])
 checks=result.get('physical_checks',{})
 required(all(checks.get(k,{}).get('status')=='met' for k in ('setup','target','maneuver')) and result.get('maneuver_completed') is True,'Physical completion not measured')
 for kind in ('setup','target','maneuver'):
  sources=checks[kind].get('sources',{})
  required(all(sources.get(name)==sha(root/name) for name in ('config.json','trace.jsonl','video_frames.jsonl')),'Physical completion source hashes differ')
  required(not checks[kind].get('missing_evidence'),'Physical completion has missing evidence')
 attempt_no=a.attempt_number
 if attempt_no is None:
  suffix=''.join(ch for ch in root.name if ch.isdigit());required(suffix,'Attempt number required');attempt_no=int(suffix)
 report={'format':'worker-delivery-audit-v1','passed':True,'case_id':a.case,'job_id':a.job,'attempt':attempt_no,'recording_id':a.recording,'frames':len(trace),'source_result_sha256':sha(result_path),'video':'raw.mkv','video_sha256':sha(videos['raw']),'trace':'traffic_spec/trace.json','trace_sha256':sha(core_path),'checks':{k:True for k in CHECKS},'pixel_review_sha256':sha(root/'pixel-review.json'),'scope':'CPU diagnostic fixture only' if a.fixture_test else 'original saved evidence and measured physical completion; no legal verdict'}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,sort_keys=True))
if __name__=='__main__':
 try:main()
 except Exception as exc:print(type(exc).__name__+': '+str(exc),file=sys.stderr);sys.exit(1)
