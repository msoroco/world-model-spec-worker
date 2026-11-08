"""Save eight 480-frame synthetic disabled/healthy CPU source controls."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_b_engineering import NAMES,policy,rows,measure,triggers

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def main():
    summary=[]
    for state in ('faulted','healthy'):
        for candidate in NAMES:
            p=policy(state,candidate);source=rows(state,candidate)
            folder=HERE/'draft-exception-b-cases'/state/candidate
            folder.mkdir(parents=True,exist_ok=True)
            source_path=folder/'source-rows.jsonl'
            source_path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in source))
            for name,value in (('construction.json',p),('measurement.json',measure(source,p)),
                               ('trigger-measurement.json',triggers(source,p))):
                write(folder/name,value)
            negatives=[]
            for kind in ('fault_state','frame_identity'):
                changed=json.loads(json.dumps(source))
                if kind=='fault_state':
                    changed[110]['fault_injection_applied']=not changed[110]['fault_injection_applied']
                else:changed[110]['native_frame']+=1
                try:measure(changed,p)
                except ValueError as exc:negatives.append({'kind':kind,'rejected':True,'reason':str(exc)})
                else:raise AssertionError('Negative accepted: '+kind)
            write(folder/'negative-receipts.json',negatives)
            receipt={'format':'c10052-exception-b-source-receipt-v1','state':state,
                'candidate_id':candidate,'source_sha256':sha(source_path),
                'construction_sha256':sha(folder/'construction.json'),
                'measurement_sha256':sha(folder/'measurement.json'),
                'trigger_sha256':sha(folder/'trigger-measurement.json'),
                'negative_sha256':sha(folder/'negative-receipts.json'),
                'source_kind':'synthetic_cpu_fixture','accepted':False}
            write(folder/'receipt.json',receipt)
            summary.append({'state':state,'candidate_id':candidate,
                'receipt':(folder/'receipt.json').relative_to(HERE).as_posix(),
                'receipt_sha256':sha(folder/'receipt.json')})
    path=HERE/'exception-b-source-summary.json'
    write(path,{'format':'c10052-exception-b-source-summary-v1','cases':2,
        'candidates':8,'results':summary,'selected':False,
        'original_native_capture_executed':False,'accepted':False})
    print(json.dumps({'cases':2,'candidates':8,'summary_sha256':sha(path)}))

if __name__=='__main__':main()
