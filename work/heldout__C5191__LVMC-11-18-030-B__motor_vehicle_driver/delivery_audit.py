"""Independent C5191 original-source and four-camera delivery audit."""
import argparse,hashlib,json
from pathlib import Path
from turn_finalizer import measure_marked_turn
CAMERAS=('overview','approach','reference_corner','driver_reference')
SOURCES=('video_frames.jsonl','trace.jsonl','turn_originals.jsonl','turn_scene_context.json')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def audit_attempt(attempt,report,*,decoder=None):
 root=Path(attempt);report=json.loads(Path(report).read_text()) if not isinstance(report,dict) else report;case=report.get('case_id','')
 if not case.startswith('heldout__C5191__LVMC-11-18-030-B__motor_vehicle_driver__'):raise ValueError('Wrong C5191 exact source audit case')
 source_hashes=report['measurements']['marked_turn_observation']['sources']
 if set(source_hashes)!=set(SOURCES):raise ValueError('C5191 original source inventory differs')
 for name,expected in source_hashes.items():
  if not (root/name).is_file() or digest(root/name)!=expected:raise ValueError('C5191 original source hash differs: '+name)
 measured=measure_marked_turn(root)
 if measured!=report['measurements']['marked_turn_observation']['value']:raise ValueError('C5191 original turn measurement differs')
 mapping,trace,original=(rows(root/n) for n in ('video_frames.jsonl','trace.jsonl','turn_originals.jsonl'))
 if not mapping or not len(mapping)==len(trace)==len(original):raise ValueError('C5191 original frames incomplete')
 for i,(f,t,o) in enumerate(zip(mapping,trace,original)):
  if f['video_frame']!=i or (t['frame'],t['time_s'])!=(f['carla_frame'],f['time_s']) or (o['frame'],o['time_s'])!=(f['carla_frame'],f['time_s']):raise ValueError('C5191 original frame join differs')
 if decoder is None:
  from worker_exchange.media import audit as decoder
 camera={}
 for name in CAMERAS:
  path=root/(name+'.mkv')
  if not path.is_file():raise ValueError('Missing C5191 original camera: '+name)
  decoded=decoder(path,len(mapping),mapping_sha256=digest(root/'video_frames.jsonl'))
  if decoded.get('frames')!=len(mapping):raise ValueError('C5191 camera frame count differs: '+name)
  camera[name]={'source_sha256':digest(path),'decode':decoded}
 return {'format':'worker-C5191-source-audit','case_id':case,'source_hashes':source_hashes,'frame_count':len(mapping),'camera_decodes':camera,'measurement_recomputed':True,'physical_visibility_claimed':False,'legal_exception_claimed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--case',required=True);p.add_argument('--attempt',required=True);p.add_argument('--report',required=True);a=p.parse_args();r=audit_attempt(a.attempt,a.report)
 if r['case_id']!=a.case:raise ValueError('C5191 audit case argument differs')
 print(json.dumps({'case_id':a.case,'frame_count':r['frame_count'],'measurement_recomputed':True,'camera_sources':list(r['camera_decodes']),'physical_visibility_claimed':False}))
