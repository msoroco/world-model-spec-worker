"""Independent saved-evidence delivery audit. CPU fixtures test code, not Native acceptance."""
import argparse, hashlib, json, subprocess
from pathlib import Path

CHECKS=('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):
 if not path.is_file():raise ValueError('Missing required source: '+str(path.name))
 return json.loads(path.read_text())
def rows(path):
 if not path.is_file():raise ValueError('Missing required source: '+str(path.name))
 return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
def need(condition,message):
 if not condition:raise ValueError(message)
def video_frame(video,index,width,height):
 command=['ffmpeg','-nostdin','-v','error','-i',str(video),'-vf',f'select=eq(n\\,{index})','-frames:v','1','-f','image2pipe','-vcodec','ppm','pipe:1']
 result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
 header=b'P6\n'+str(width).encode()+b' '+str(height).encode()+b'\n255\n'
 need(result.stdout.startswith(header) and len(result.stdout)==len(header)+width*height*3,'Pixel frame decode length differs')
 return result.stdout[len(header):]
def audit(case,job,attempt_number,recording,root):
 root=Path(root).resolve();result=load(root/'result.json');seal=load(root/'capture-seal.json');config=load(root/'config.json');mapping=rows(root/'video_frames.jsonl');motion=rows(root/'trace.jsonl');core=load(root/'traffic_spec/trace.json');video=root/'raw.mkv'
 need(video.is_file(),'Missing required source: raw.mkv')
 need(result.get('case_id')==case and config.get('selected_case_id')==case,'Result/config case identity mismatch')
 need(len(mapping)==config.get('duration_s')*config.get('rate_hz'),'Original duration or rate incomplete')
 need(result.get('provenance_kind')=='native' and result.get('diagnostic_fixture') is False and seal.get('format')=='worker-sealed-capture-v2' and seal.get('provenance_kind')=='native' and seal.get('diagnostic_fixture') is False,'Native source provenance missing')
 for name,checksum in seal.get('sources',{}).items():
  source=(root/name).resolve();need(root in source.parents and source.is_file() and checksum==digest(source),'Sealed Native source changed: '+name)
 need({'trace.jsonl','video_frames.jsonl','overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'} <= set(seal.get('sources',{})),'Sealed Native source manifest incomplete')
 need(seal.get('events')==['capture_finished','encoders_closed','restoration_verified'] and seal.get('restoration',{}).get('restored') is True and all(code==0 for code in seal.get('encoder_exit_codes',{}).values()),'Native capture closure incomplete')
 need(seal.get('frames')==len(mapping),'Sealed Native frame count differs')
 spec=load(Path(__file__).with_name('delivery-audit-spec.json'));case_spec=spec['cases'][case];required=case_spec['required_participants'];extra=case_spec.get('participant_sources',{})
 need(len(mapping)>0 and len(motion)==len(mapping),'Original participant history incomplete')
 for i,(frame,source) in enumerate(zip(mapping,motion)):
  need(frame.get('video_frame')==i and frame.get('carla_frame')==source.get('frame') and abs(frame['time_s']-source['time_s'])<1e-4,'Original frame/time join failed')
  participants=source.get('participants',{})
  for role in required:
   if role=='subject':need(source.get('position_m') or participants.get('subject'),'Missing required participant: subject')
   else:need(participants.get(role),'Missing required participant: '+role)
 for role,source in extra.items():
  source_rows=rows(root/source['path']);need(len(source_rows)==len(mapping),'Missing required participant history: '+role)
  for frame,participant in zip(mapping,source_rows):need(participant.get('frame')==frame.get('carla_frame') and participant.get(source['key']),'Missing required participant: '+role)
 scenes=core.get('scenes',[]);need(len(scenes)==len(mapping),'Core scene count differs')
 for i,(frame,scene) in enumerate(zip(mapping,scenes)):need(scene.get('t')==round(frame['time_s']*1000),'Core timestamp join failed')
 try:probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=nb_read_frames,width,height','-of','json',str(video)],text=True,stderr=subprocess.PIPE))['streams'][0]
 except (subprocess.CalledProcessError,IndexError,ValueError):raise ValueError('Full video decode failed')
 need(int(probe['nb_read_frames'])==len(mapping),'Full video frame count differs')
 decode=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(video),'-c:v','ffv1','-f','matroska','pipe:1'],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 need(decode.returncode==0,'Full video decode failed')
 composition=load(root/'four-view-receipt.json');need(composition.get('format')=='synchronized-four-view-v1' and composition.get('primary_sha256')==digest(video) and composition.get('frame_map_sha256')==digest(root/'video_frames.jsonl'),'Composed primary is not source-bound')
 for name in ('overview','approach','reference_corner','driver_reference'):
  need(composition.get('sources',{}).get(name)==digest(root/(name+'.mkv')),'Composed view source changed: '+name)
 pixels=load(root/'pixel-evidence.json');need(pixels.get('format')=='worker-original-pixel-evidence-v1' and pixels.get('video_sha256')==digest(video),'Pixel evidence does not bind original video')
 annotations=pixels.get('annotations',[]);need({a.get('subject') for a in annotations}>=set(required)|set(extra),'Required participant lacks pixel evidence')
 for a in annotations:
  need(a.get('method')=='original_frame_review' and a.get('reviewer') and a.get('visible') is True,'Visible pixel review absent')
  index=a.get('video_frame');need(type(index) is int and 0<=index<len(mapping),'Pixel frame outside original map')
  box=a.get('bbox_xyxy');need(isinstance(box,list) and len(box)==4,'Missing pixel region')
  width,height=int(probe['width']),int(probe['height']);need(0<=box[0]<box[2]<=width and 0<=box[1]<box[3]<=height,'Pixel region outside decoded frame')
  im=video_frame(video,index,width,height);pixels=[im[3*(y*width+x)+channel] for y in range(box[1],box[3]) for x in range(box[0],box[2]) for channel in range(3)];need(max(pixels)-min(pixels)>5,'Relevant visible pixel region is blank')
 need(result.get('setup_confirmed') is True and result.get('behavior_attempted') is True and result.get('maneuver_completed') is True,'Physical completion failed')
 for key in ('setup','target','maneuver'):
  need(result.get('physical_checks',{}).get(key,{}).get('status')=='met','Physical completion failed: '+key)
 need(bool(result.get('target_checks')) and all(item.get('matched') is True for item in result['target_checks']),'Physical target mismatch')
 return {'format':'worker-delivery-audit-v1','passed':True,'case_id':case,'job_id':job,'attempt':attempt_number,'recording_id':recording,'frames':len(mapping),'source_result_sha256':digest(root/'result.json'),'video':'raw.mkv','video_sha256':digest(video),'trace':'traffic_spec/trace.json','trace_sha256':digest(root/'traffic_spec/trace.json'),'checks':{key:True for key in CHECKS},'pixel_evidence_sha256':digest(root/'pixel-evidence.json'),'limitations':['Physical measurements and source-backed pixel annotations require actual Native evidence; CPU fixtures test audit logic only.']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--job',required=True);p.add_argument('--attempt',required=True,type=int);p.add_argument('--recording',required=True);p.add_argument('--output',required=True);p.add_argument('--root',required=True);a=p.parse_args()
 try:
  value=audit(a.case,a.job,a.attempt,a.recording,a.root)
  target=Path(a.output);target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(value,indent=2)+'\n')
  print(json.dumps({'passed':True,'case_id':a.case,'frames':value['frames']}))
 except Exception as error:
  print(str(error));raise SystemExit(1)
if __name__=='__main__':main()
