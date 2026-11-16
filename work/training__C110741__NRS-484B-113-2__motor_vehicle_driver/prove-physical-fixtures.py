"""CPU-only source-shaped reverse completion and ownership lifecycle fixtures."""
import argparse, hashlib, json, math
from pathlib import Path

HERE=Path(__file__).resolve().parent
EVENTS=['capture_finished','encoders_closed','restoration_verified','native_exit','owner_released','saved_processing_started']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,indent=2)+'\n')
def run(suffix,kind):
 if suffix not in ('condition_a','condition_b'):raise ValueError('Unknown selected case')
 case=HERE.name+'__selected_55c68e79__'+suffix
 entry=next(e for e in read(HERE/'execution-manifest.json')['cases'] if e['case_id']==case)
 path=HERE/'diagnostic-sources'/suffix/'native_samples.jsonl'
 rows=[json.loads(line) for line in path.read_text().splitlines()]
 if len(rows)!=480:raise ValueError('Source-shaped fixture needs 480 frames')
 if kind=='lifecycle':
  return {'case_id':case,'construction_sha256':entry['construction_sha256'],'events':EVENTS,'exit_code':0,'cpu_fixture_mock':True,'original_native_motion_verified':False}
 if kind=='missing_evidence':rows=[]
 elif kind=='incomplete_motion':rows=rows[:100]
 elif kind!='complete_motion':raise ValueError('Unknown physical fixture kind')
 reverse=sum(row['signed_forward_velocity_m_s']<-.05 for row in rows)
 target=[-11.0 if suffix=='condition_a' else -14.0,-1.75]
 endpoint=rows[-1]['native_center_xy_m'] if rows else None
 distance=math.dist(endpoint,target) if endpoint else None
 stopped=bool(rows and abs(rows[-1]['signed_forward_velocity_m_s'])<=.05)
 status='unverified' if not rows else ('met' if len(rows)==480 and reverse>=10 and distance<=.4 and stopped else 'not_met')
 return {'case_id':case,'construction_sha256':entry['construction_sha256'],'cpu_fixture_mock':True,'mock_input_provenance':'synthetic_native_sample','original_native_motion_verified':False,'accepted':False,'legal_verdict_claimed':False,'provenance_kind':'native' if rows else 'missing','physical_checks':{'maneuver':{'status':status,'method':'joined Native-shaped reverse velocity, endpoint and 480 frame count','sources':['diagnostic-sources/'+suffix+'/native_samples.jsonl'] if rows else ['missing diagnostic Native samples']}},'maneuver_completed':status=='met','realized_observables':{'reverse_frames':reverse,'endpoint_distance_m':distance,'stopped_at_endpoint':stopped,'sample_count':len(rows)} if rows else {},'retained_source_sha256':{'native_samples.jsonl':sha(path)} if rows else {}}
def main():
 a=argparse.ArgumentParser();a.add_argument('--suffix',required=True);a.add_argument('--kind',required=True);a.add_argument('--output',required=True);args=a.parse_args()
 result=run(args.suffix,args.kind);write(args.output,result);print(json.dumps({'case_id':result['case_id'],'kind':args.kind,'status':result.get('physical_checks',{}).get('maneuver',{}).get('status','lifecycle'),'cpu_fixture_mock':True,'original_native_motion_verified':False}))
if __name__=='__main__':main()
