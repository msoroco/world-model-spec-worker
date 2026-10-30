"""Independent saved-evidence audit for one canonical delivery recording.

This script reads sealed original evidence and processed Core output. It never
runs CARLA, assigns a legal verdict, or alters original acquisition.
"""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

CHECKS = ('native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion')

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as stream:
  for block in iter(lambda:stream.read(1048576),b''):h.update(block)
 return h.hexdigest()

def read(path):
 return json.loads(path.read_text())

def rows(path):
 return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

def require(condition,message):
 if not condition:raise ValueError(message)

def local(root,path):
 candidate=(root/path).resolve()
 require(root==candidate or root in candidate.parents,'Evidence path escapes canonical attempt')
 require(candidate.is_file(),'Missing required evidence: '+str(path))
 return candidate

def native_source(original,analysis,fixture_test=False):
 provenance=read(local(original,'acquisition-provenance.json'))
 seal=read(local(original,'capture-seal.json'))
 expected_kind='synthetic_fixture' if fixture_test else 'native'
 expected_diagnostic=bool(fixture_test)
 require(provenance.get('provenance_kind')==expected_kind and provenance.get('diagnostic_fixture') is expected_diagnostic,
         'Rejected non-native or diagnostic source')
 require(seal.get('format')=='worker-sealed-capture-v2' and seal.get('provenance_kind')==expected_kind
         and seal.get('diagnostic_fixture') is expected_diagnostic,'Missing valid capture seal')
 require(seal.get('restoration',{}).get('restored') is True,'Native world restoration unverified')
 for name in ('trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
              'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv'):
  expected=seal.get('sources',{}).get(name)
  require(expected and sha(local(original,name))==expected and sha(local(analysis,name))==expected,
          'Original source hash changed: '+name)
 composed=read(local(analysis,'four-view-receipt.json'))
 require(composed.get('format')=='synchronized-four-view-v1' and
         composed.get('frame_map_sha256')==sha(analysis/'video_frames.jsonl') and
         composed.get('primary_sha256')==sha(local(analysis,'raw.mkv')),
         'Composed primary video source receipt differs')
 for name in ('overview','approach','reference_corner','driver_reference'):
  require(composed.get('sources',{}).get(name)==sha(analysis/(name+'.mkv')),
          'Composed camera source differs: '+name)
 return seal

def all_participants(root,frames):
 evidence=rows(local(root,'capture/evidence.jsonl'))
 require(len(evidence)==frames,'Original acquisition omits frames or participants')
 all_ids=set()
 for item in evidence:
  original=item.get('original_observations',{})
  participants=original.get('participants')
  inventory=original.get('scene_actor_inventory',[])
  require(isinstance(participants,list) and participants,'Missing original participant inventory')
  require(item.get('participant_inventory') or original.get('participant_inventory'),
          'Original participant inventory scope missing')
  observed={p.get('actor_id') for p in participants}
  expected={p.get('id') for p in inventory if str(p.get('type','')).startswith(('vehicle.','walker.'))}
  require(None not in observed and observed==expected,'Original participant inventory differs from live actors')
  for p in participants:
   require(isinstance(p.get('body_vertices_m'),list) and len(p['body_vertices_m'])>=4,
           'Participant body history incomplete')
  all_ids.update(observed)
 require(all_ids,'No original participants')
 return evidence

def time_join(root,evidence,frames):
 mapping=rows(local(root,'video_frames.jsonl'))
 trace=rows(local(root,'trace.jsonl'))
 core=read(local(root,'traffic_spec/trace.json')).get('scenes',[])
 require(len(mapping)==len(trace)==len(evidence)==len(core)==frames,
         'Original frame/Core trace count mismatch')
 previous=-math.inf
 for index,(m,t,e,c) in enumerate(zip(mapping,trace,evidence,core)):
  stamp=m.get('time_s')
  require(m.get('video_frame')==index and isinstance(stamp,(int,float)) and math.isfinite(stamp)
          and stamp>previous,'Original frame map has gaps or invalid time')
  require(t.get('frame')==m.get('carla_frame')
          and abs(t.get('time_s',math.inf)-stamp)<1e-4
          and e.get('original_frame')==m.get('carla_frame')
          and abs(e.get('recording_time_s',math.inf)-stamp)<1e-4
          and c.get('t')==round(stamp*1000),
          'Original frame/Core timestamp join failed')
  previous=stamp
 return core

def full_video_decode(root,frames):
 video=local(root,'raw.mkv')
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-count_frames','-select_streams','v:0',
  '-show_entries','stream=width,height,nb_read_frames','-of','json',str(video)],text=True))
 streams=probe.get('streams',[])
 require(len(streams)==1 and int(streams[0].get('nb_read_frames',-1))==frames,
         'Primary video frame count differs')
 decoded=subprocess.run(['ffmpeg','-nostdin','-v','error','-xerror','-i',str(video),'-f','image2pipe','-c:v','ppm','-pix_fmt','rgb24','pipe:1'],
                        stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 require(decoded.returncode==0,'Full primary video decode failed: '+decoded.stderr.decode(errors='replace')[-400:])
 return video

def actual_pixels(root,video,frames):
 annotations=read(local(root,'pixel-visibility.json'))
 require(annotations.get('format')=='worker-reviewed-pixel-visibility-v1'
         and annotations.get('video_sha256')==sha(video)
         and annotations.get('reviewed') is True
         and annotations.get('reviewer') and annotations.get('case_id'),
         'Missing source-bound relevant pixel review')
 samples=annotations.get('samples',[])
 require(len(samples)>=3,'Pixel review must cover approach, interaction and clearance')
 phase_set=set()
 for sample in samples:
  frame=sample.get('frame');x,y,w,h=sample.get('roi',[None]*4)
  require(type(frame)==int and 0<=frame<frames and all(type(v)==int for v in (x,y,w,h))
          and x>=0 and y>=0 and w>=8 and h>=8
          and sample.get('subject') and sample.get('phase') in ('approach','interaction','clearance'),
          'Invalid relevant pixel region/phase')
  phase_set.add(sample['phase'])
  command=['ffmpeg','-nostdin','-v','error','-i',str(video),'-vf',
           'select=eq(n\\,'+str(frame)+'),crop='+str(w)+':'+str(h)+':'+str(x)+':'+str(y),
           '-frames:v','1','-f','image2pipe','-c:v','ppm','-pix_fmt','rgb24','pipe:1']
  output=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  parts=output.stdout.split(b'\n',3)
  require(output.returncode==0 and len(parts)==4 and parts[0]==b'P6' and len(parts[3])==w*h*3,'Relevant pixel crop failed: '+output.stderr.decode(errors='replace')[-300:])
  values=parts[3]
  require(max(values)-min(values)>=12 and len(set(values))>=16,
          'Relevant pixel region lacks visible content')
 require(phase_set=={'approach','interaction','clearance'},
         'Pixel review omits a required phase')
 return samples

def physical_completion(root):
 result=read(local(root,'result.json'))
 checks=result.get('physical_checks',{})
 for name in ('setup','target','maneuver'):
  sources=checks.get(name,{}).get('sources',{})
  require(isinstance(sources,dict) and sources,'Physical check lacks original source hashes: '+name)
  for path,checksum in sources.items():
   require(sha(local(root,path))==checksum,'Physical check source hash changed: '+path)
 require(result.get('setup_confirmed') is True and result.get('behavior_attempted') is True
         and result.get('maneuver_completed') is True
         and all(checks.get(k,{}).get('status')=='met' for k in ('setup','target','maneuver')),
         'Physical setup, target, or maneuver incomplete')
 require(result.get('analysis_complete',True) is True,'Saved analysis incomplete')
 return result

def audit(args):
 recording=Path(args.recording).resolve()
 original=recording/'evidence'
 root=Path(args.analysis).resolve() if args.analysis else original
 require(original.is_dir() and root.is_dir() and read(local(recording,'metadata.json')).get('recording_id')==recording.name,
         'Canonical recording identity missing')
 metadata=read(recording/'metadata.json')
 require(metadata.get('job_id')==args.job and metadata.get('attempt')==args.attempt
         and metadata.get('case_id')==args.case,'Canonical job, attempt, or case mismatch')
 seal=native_source(original,root,args.fixture_test)
 frames=seal.get('frames')
 require(type(frames)==int and frames>0,'Native frame count invalid')
 config=read(local(root,'config.json'))
 require(frames==config.get('duration_s',0)*config.get('rate_hz',0),
         'Original duration or sampling rate incomplete')
 evidence=all_participants(root,frames)
 time_join(root,evidence,frames)
 video=full_video_decode(root,frames)
 pixels=actual_pixels(root,video,frames)
 result=physical_completion(root)
 trace=local(root,'traffic_spec/trace.json')
 require(read(root/'pixel-visibility.json')['case_id']==args.case,'Pixel review selects another case')
 output=Path(args.output).resolve()
 require(root in output.parents and not output.exists(),'Audit output must be a new file inside saved analysis')
 report={'format':'worker-delivery-audit-v1','passed':True,'case_id':args.case,
         'job_id':args.job,'attempt':args.attempt,'recording_id':recording.name,'frames':frames,
         'source_result_sha256':sha(root/'result.json'),'video':'raw.mkv','video_sha256':sha(video),
         'trace':'traffic_spec/trace.json','trace_sha256':sha(trace),
         'pixel_review_sha256':sha(root/'pixel-visibility.json'),
         'pixel_samples':len(pixels),'checks':{name:True for name in CHECKS},
         'legal_acceptance_claimed':False,'fixture_test':args.fixture_test}
 output.write_text(json.dumps(report,indent=2)+'\n')
 return report

def main():
 p=argparse.ArgumentParser()
 p.add_argument('--case',required=True);p.add_argument('--job',type=int,required=True)
 p.add_argument('--attempt',type=int,required=True);p.add_argument('--recording',required=True)
 p.add_argument('--output',required=True);p.add_argument('--analysis');p.add_argument('--fixture-test',action='store_true')
 args=p.parse_args()
 try:print(json.dumps(audit(args),indent=2))
 except (ValueError,KeyError,OSError,subprocess.CalledProcessError) as error:
  p.exit(1,type(error).__name__+': '+str(error)+'\n')

if __name__=='__main__':main()
