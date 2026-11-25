"""Independent exact-case source audit; diagnostics never assert physical delivery."""
import argparse,hashlib,json,subprocess
from pathlib import Path
NAMES=('overview','approach','reference_corner','driver_reference')
def need(root,name):
 p=root/name
 if not p.is_file():raise ValueError('Missing delivery source: '+name)
 return p
def rows(p):return [json.loads(s) for s in p.read_text().splitlines()]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def audit(root,case,diagnostic):
 root=Path(root)
 config=json.loads(need(root,'config.json').read_text())
 if config['case_id']!=case:raise ValueError('Wrong exact delivery case')
 if not diagnostic:
  need(root,'capture-seal.json');need(root,'native-capture-report.json')
 names=('native-cycle-frames.jsonl','native-map-readback.json','standing-vehicle.json',
        'trace.jsonl','video_frames.jsonl','capture/evidence.jsonl','context.json')
 evidence={name:sha(need(root,name)) for name in names}
 bicycle,trace,frames,capture=(rows(root/name) for name in (names[0],names[3],names[4],names[5]))
 if any(len(s)!=600 for s in (bicycle,trace,frames,capture)):
  raise ValueError('Incomplete 600-frame delivery source')
 context=json.loads((root/'context.json').read_text())
 if context.get('legal_verdict') is not None:raise ValueError('Legal judgment must remain unresolved')
 for i,(b,t,f,c) in enumerate(zip(bicycle,trace,frames,capture)):
  frame=b['native_frame']
  if b['frame']!=i or t['frame']!=frame or f['native_frame']!=frame or c['original_frame']!=frame or abs(b['time_s']-f['time_s'])>1e-4 or any(f['camera_native_frames'][n]!=frame for n in NAMES):
   raise ValueError('Delivery source time join failed')
  if b['source_kind'] != ('synthetic_native_sample' if diagnostic else 'native_actor'):
   raise ValueError('Delivery provenance differs')
 if context['source_kind'] != ('synthetic_cpu' if diagnostic else 'original_native'):
  raise ValueError('Delivery context provenance differs')
 for name in NAMES:
  p=need(root,name+'.mkv')
  run=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-count_frames','-show_entries',
      'stream=nb_read_frames','-of','default=nw=1:nk=1',str(p)],capture_output=True,text=True,check=True)
  if int(run.stdout.strip())!=600:raise ValueError('Incomplete delivery video: '+name)
  evidence[name+'.mkv']=sha(p)
 return {'format':'c230259-independent-delivery-audit-v1','case_id':case,
         'checks':['native_source','all_participants','time_join','full_video_decode','actual_pixels','physical_completion'],
         'source_hashes':evidence,'frames':600,'diagnostic_fixture':diagnostic,
         'original_native_observed':not diagnostic,'display_pixels_reviewed':False,
         'bicycle_identity_reviewed':False,'physical_acceptance':False,'legal_verdict':None}
if __name__=='__main__':
 p=argparse.ArgumentParser()
 for name in ('attempt','case','output'):p.add_argument('--'+name,required=True)
 p.add_argument('--diagnostic',action='store_true');a=p.parse_args()
 result=audit(a.attempt,a.case,a.diagnostic)
 Path(a.output).write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'case_id':a.case,'frames':600,'diagnostic_fixture':a.diagnostic,'physical_acceptance':False}))
