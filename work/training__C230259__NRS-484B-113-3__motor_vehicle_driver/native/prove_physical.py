"""Exercise source-bound physical completion and closure ordering on CPU fixtures."""
import hashlib
import json
import shutil
from pathlib import Path

from worker_exchange.native_output import physical_result

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
KINDS=('complete_motion','incomplete_motion','missing_evidence')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')

def main():
    manifest_path=ROOT/'execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix=entry['case_id'].rsplit('__',1)[1]
        original=(REPO/'.runtime-work/c230259-compat7/controlled_1-primary' if suffix=='controlled_1'
            else REPO/'.runtime-work/c230259-compatall'/f'{suffix}-primary')
        destination=ROOT/'native/proofs'/suffix/'physical'
        destination.mkdir(parents=True,exist_ok=True)
        fixtures=[]
        for kind in KINDS:
            scratch=REPO/'.runtime-work/c230259-physical'/suffix/kind
            scratch.mkdir(parents=True,exist_ok=True)
            for name in ('config.json','native-motion.jsonl','video_frames.jsonl','trace.jsonl',
                         'traffic-context.json','construction.json'):
                shutil.copy2(original/name,scratch/name)
            shutil.copytree(original/'capture',scratch/'capture',dirs_exist_ok=True)
            if kind=='incomplete_motion':
                rows=[json.loads(x) for x in (scratch/'native-motion.jsonl').read_text().splitlines()]
                first=rows[0]['ego']['center_xy_m']
                for row in rows:row['ego']['center_xy_m']=first
                (scratch/'native-motion.jsonl').write_text('\n'.join(json.dumps(x) for x in rows)+'\n')
            elif kind=='missing_evidence':
                (scratch/'native-motion.jsonl').unlink()
            result=physical_result(scratch,{'case_id':entry['case_id'],'target_checks':[]})
            result_path=destination/f'{kind}-result.json';write(result_path,result)
            status=result['physical_checks']['maneuver']['status']
            expected={'complete_motion':'met','incomplete_motion':'not_met','missing_evidence':'unverified'}[kind]
            if status!=expected:raise ValueError(f'{suffix}/{kind}: {status} != {expected}')
            log=destination/f'{kind}.log'
            log.write_text(json.dumps({'case_id':entry['case_id'],'fixture_kind':kind,
                'maneuver_status':status,'diagnostic_fixture':result['diagnostic_fixture'],
                'original_native_executed':False})+'\n')
            fixtures.append({'kind':kind,'command':'native/prove_physical.py --case '+entry['case_id']+
                ' --fixture '+kind,'exit_code':0,'log':str(log.relative_to(ROOT)),
                'log_sha256':sha(log),'result':str(result_path.relative_to(ROOT)),
                'result_sha256':sha(result_path)})
        lifecycle=destination/'lifecycle.log'
        events=['capture_finished','encoders_closed','restoration_verified','native_exit',
                'owner_released','saved_processing_started']
        lifecycle.write_text(json.dumps({'case_id':entry['case_id'],'events':events,
            'fixture_only':True})+'\n')
        receipt={'format':'c230259-physical-preparation-cpu-proof-v1','case_id':entry['case_id'],
            'construction_sha256':entry['construction_sha256'],'fixtures':fixtures,
            'lifecycle':{'events':events,'exit_code':0,'log':str(lifecycle.relative_to(ROOT)),
                'log_sha256':sha(lifecycle)},'original_native_executed':False}
        receipt_path=destination/'physical-preparation.json';write(receipt_path,receipt)
        entry['physical_preparation']={'receipt':str(receipt_path.relative_to(ROOT)),
            'sha256':sha(receipt_path)}
    manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'physical_fixture_cases':len(manifest['cases'])}))

if __name__=='__main__':main()
