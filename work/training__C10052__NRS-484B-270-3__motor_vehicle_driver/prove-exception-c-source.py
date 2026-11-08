"""Save eight controlled synthetic traffic-conflict source constructions."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from exception_c_engineering import NAMES,body,measure,policy,rows,triggers

def write(path,value):
    path.write_text(json.dumps(value,indent=2,sort_keys=True,allow_nan=False)+'\n')
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    root=HERE/'draft-exception-c-cases';receipts=[]
    for response in ('avoid','no_conflict'):
        for candidate in NAMES:
            folder=root/response/candidate;folder.mkdir(parents=True,exist_ok=True)
            p=policy(response,candidate);source=rows(response,candidate)
            write(folder/'construction.json',p)
            (folder/'source-rows.jsonl').write_text(''.join(
                json.dumps(row,sort_keys=True,allow_nan=False)+'\n' for row in source))
            result=measure(source,p);trigger=triggers(source,p)
            assert result['synthetic_avoidance_geometry']
            write(folder/'measurement.json',result)
            write(folder/'trigger-measurement.json',trigger)
            changed=[dict(row) for row in source];changed[200]['native_frame']+=1
            try:measure(changed,p)
            except ValueError as exc:frame_error=str(exc)
            else:raise AssertionError('Changed frame accepted')
            absent=[dict(row) for row in source]
            if response=='avoid':
                for row in absent:
                    row['conflict_actor_id']=None
                    row['conflict_actor_body_xy']=[]
                    row['conflict_actor_active']=False
            else:
                for row in absent[165:236]:
                    row['conflict_actor_id']=221
                    row['conflict_actor_body_xy']=body(0,-1.5,4.6,1.8)
                    row['conflict_actor_active']=True
            negative=measure(absent,p)
            assert negative['synthetic_avoidance_geometry'] is False
            receipt={'format':'c10052-exception-c-source-receipt-v1',
                'case_suffix':p['case_suffix'],'candidate_id':candidate,
                'source_kind':'synthetic_cpu_fixture','accepted':False,
                'construction_sha256':sha(folder/'construction.json'),
                'source_sha256':sha(folder/'source-rows.jsonl'),
                'measurement_sha256':sha(folder/'measurement.json'),
                'trigger_sha256':sha(folder/'trigger-measurement.json'),
                'frame_mutation_rejected':frame_error,
                'causal_negative':negative}
            write(folder/'receipt.json',receipt);receipts.append(receipt)
    write(HERE/'exception-c-source-summary.json',{
        'format':'c10052-exception-c-source-summary-v1','cases':2,
        'candidates_per_case':4,'positive_source_receipts':8,
        'causal_negatives':8,'changed_frame_negatives':8,
        'controlled_pairs':4,'receipts':receipts,
        'original_native_verified':False,'legal_exception_verified':False,'accepted':False})
    print(json.dumps({'passed':True,'positive_source_receipts':8,'controlled_pairs':4}))
if __name__=='__main__':main()
