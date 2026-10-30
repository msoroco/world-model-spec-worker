"""CPU-only positive and timestamp-negative audit fixture for each selected case."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
AID=Path(__file__).resolve().parent.name
AUDIT=Path(__file__).resolve().parent/'delivery_audit.py'

def put(path,value):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(value,indent=2)+'\n')

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def fixture(case,root):
 recording=root/'recording-cpu-fixture';e=recording/'evidence'
 e.mkdir(parents=True)
 (e/'capture').mkdir()
 put(recording/'metadata.json',{'recording_id':recording.name,'job_id':17,'attempt':1,'case_id':case})
 subprocess.run(['ffmpeg','-nostdin','-v','error','-f','lavfi','-i','testsrc2=size=64x64:rate=20',
                 '-frames:v','3','-c:v','ffv1',str(e/'raw.mkv')],check=True)
 for name in ('overview','approach','reference_corner','driver_reference'):
  shutil.copyfile(e/'raw.mkv',e/(name+'.mkv'))
 times=(0,0.05,0.1)
 (e/'video_frames.jsonl').write_text(''.join(json.dumps({'video_frame':i,'carla_frame':100+i,'time_s':t})+'\n' for i,t in enumerate(times)))
 (e/'trace.jsonl').write_text(''.join(json.dumps({'frame':100+i,'time_s':t})+'\n' for i,t in enumerate(times)))
 put(e/'traffic_spec/trace.json',{'scenes':[{'t':round(t*1000)} for t in times]})
 body=[[0,0,0],[1,0,0],[1,1,0],[0,1,0]]
 (e/'capture/evidence.jsonl').write_text(''.join(json.dumps({'original_frame':100+i,'recording_time_s':t,
  'participant_inventory':'all original live vehicle and walker actors',
  'original_observations':{'participants':[{'actor_id':3,'body_vertices_m':body}],
   'scene_actor_inventory':[{'id':3,'type':'vehicle.test'}]}})+'\n' for i,t in enumerate(times)))
 put(e/'acquisition-provenance.json',{'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})
 put(e/'config.json',{'duration_s':0.15,'rate_hz':20})
 put(e/'result.json',{'setup_confirmed':True,'behavior_attempted':True,'maneuver_completed':True,
   'analysis_complete':True,'physical_checks':{name:{'status':'met','sources':{'trace.jsonl':digest(e/'trace.jsonl'),
    'video_frames.jsonl':digest(e/'video_frames.jsonl')}} for name in ('setup','target','maneuver')}})
 put(e/'pixel-visibility.json',{'format':'worker-reviewed-pixel-visibility-v1','video_sha256':digest(e/'raw.mkv'),
   'reviewed':True,'reviewer':'CPU fixture reviewer; synthetic test only','case_id':case,
   'samples':[{'frame':i,'roi':[0,0,64,64],'subject':'fixture subject','phase':phase}
              for i,phase in enumerate(('approach','interaction','clearance'))]})
 put(e/'four-view-receipt.json',{'format':'synchronized-four-view-v1',
   'frame_map_sha256':digest(e/'video_frames.jsonl'),'primary_sha256':digest(e/'raw.mkv'),
   'sources':{name:digest(e/(name+'.mkv')) for name in ('overview','approach','reference_corner','driver_reference')}})
 names=('trace.jsonl','video_frames.jsonl','capture/evidence.jsonl',
        'overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')
 put(e/'capture-seal.json',{'format':'worker-sealed-capture-v2','provenance_kind':'synthetic_fixture',
   'diagnostic_fixture':True,'restoration':{'restored':True},'frames':3,
   'sources':{name:digest(e/name) for name in names}})
 return recording

def test(case,slug):
 temp=ROOT/'.runtime-work'/AID/('audit-fixture-'+slug)
 if temp.exists():shutil.rmtree(temp)
 recording=fixture(case,temp)
 positive=[str(ROOT/'.venv-cpu/bin/python'),str(AUDIT),'--case',case,'--job','17','--attempt','1',
           '--recording',str(recording),'--fixture-test','--output',str(recording/'evidence/audit-positive.json')]
 success=subprocess.run(positive,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 if success.returncode:raise RuntimeError('positive '+case+' '+success.stdout[-1000:])
 mapping=recording/'evidence/video_frames.jsonl'
 rows=[json.loads(x) for x in mapping.read_text().splitlines()]
 rows[1]['time_s']=0.06
 mapping.write_text(''.join(json.dumps(x)+'\n' for x in rows))
 negative=positive[:-1]+[str(recording/'evidence/audit-negative.json')]
 failure=subprocess.run(negative,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 if failure.returncode!=1 or 'Original source hash changed: video_frames.jsonl' not in failure.stdout:
  raise RuntimeError('negative '+case+' '+failure.stdout[-1000:])
 return positive,success.stdout,negative,failure.stdout

if __name__=='__main__':
 manifest=json.loads((Path(__file__).parent/'execution-manifest.json').read_text())
 for item in manifest['cases']:
  case=item['case_id'];slug=case.split('__')[-1]
  positive,good,negative,bad=test(case,slug)
  folder=Path(__file__).parent
  (folder/'receipts'/('delivery-positive-'+slug+'.log')).write_text('CPU synthetic fixture only; no physical acceptance.\n'+good)
  (folder/'receipts'/('delivery-negative-'+slug+'.log')).write_text('CPU synthetic fixture only; no physical acceptance.\n'+bad)
  item['delivery_acceptance']={'case_id':case,'sets':['demo-test','full-test'],
    'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
    'script':'delivery_audit.py','script_sha256':digest(AUDIT),
    'command':'python3.11 '+str(AUDIT.relative_to(ROOT))+' --case '+case+
      ' --job "$JOB_ID" --attempt "$ATTEMPT" --recording "$RECORDING" --output "$RECORDING/evidence/delivery-audit.json"',
    'test_log':'receipts/delivery-positive-'+slug+'.log',
    'test_log_sha256':digest(folder/'receipts'/('delivery-positive-'+slug+'.log')),
    'test_exit_code':0,'negative_command':' '.join(negative),
    'negative_log':'receipts/delivery-negative-'+slug+'.log',
    'negative_log_sha256':digest(folder/'receipts'/('delivery-negative-'+slug+'.log')),
    'negative_exit_code':1,'negative_expected_error':'Original source hash changed: video_frames.jsonl'}
  print('AUDIT PASS',case,flush=True)
 (folder/'execution-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
