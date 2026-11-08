"""Save controlled officer-direction sources and deliberate mutation negatives."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_e_engineering import CANDIDATES,direction,policy,rows,measure,triggers

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,value):path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

def main():
    results=[]
    for state in ('directed','routine'):
        for candidate in CANDIDATES:
            folder=HERE/'draft-exception-e-cases'/state/candidate
            folder.mkdir(parents=True,exist_ok=True)
            p=policy(state,candidate);packet=direction(state);source=rows(state,candidate)
            write(folder/'construction.json',p)
            write(folder/'officer-direction.json',packet)
            (folder/'source-rows.jsonl').write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in source))
            write(folder/'measurement.json',measure(source,packet,p))
            write(folder/'trigger-measurement.json',triggers(source,p))
            negatives=[]
            for kind in ('packet_issuer','packet_interval','officer_identity','command',
                         'direction_join','driver_response','body_path','frame_identity'):
                modified=json.loads(json.dumps(source));other=json.loads(json.dumps(packet))
                if kind=='packet_issuer':other['issuer']='driver_self_report'
                elif kind=='packet_interval':other['end_frame']=210
                elif kind=='officer_identity':modified[130]['officer_id']='wrong-officer'
                elif kind=='command':other['command']='unrelated_command'
                elif kind=='direction_join':modified[130]['direction_id']='wrong-direction'
                elif kind=='driver_response':modified[130]['driver_response']='opposite_action'
                elif kind=='body_path':modified[130]['ego_body_xy'][0][1]-=1
                else:modified[130]['native_frame']+=1
                try:measure(modified,other,p)
                except ValueError as exc:negatives.append({'kind':kind,'rejected':True,'reason':str(exc)})
                else:raise AssertionError('Negative accepted: '+kind)
            write(folder/'negative-receipts.json',negatives)
            receipt={'format':'c10052-exception-e-source-receipt-v1','state':state,
                     'candidate_id':candidate,'source_kind':'synthetic_cpu_fixture',
                     'accepted':False,'hashes':{name:sha(folder/name) for name in
                         ('construction.json','officer-direction.json','source-rows.jsonl',
                          'measurement.json','trigger-measurement.json','negative-receipts.json')}}
            write(folder/'receipt.json',receipt)
            results.append({'state':state,'candidate_id':candidate,
                'receipt':(folder/'receipt.json').relative_to(HERE).as_posix(),
                'receipt_sha256':sha(folder/'receipt.json')})
    path=HERE/'exception-e-source-summary.json'
    write(path,{'format':'c10052-exception-e-source-summary-v1','cases':2,
                'candidates':8,'results':results,'selected':False,
                'original_native_capture_executed':False,'accepted':False})
    print(json.dumps({'cases':2,'candidates':8,'summary_sha256':sha(path)}))

if __name__=='__main__':main()
