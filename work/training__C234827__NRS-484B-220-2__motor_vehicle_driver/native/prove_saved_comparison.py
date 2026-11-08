"""Retain source-bound synthetic rotary saved pair and altered controls."""
import json
from pathlib import Path
import shutil
import tempfile

from compare_saved import compare
from measure_saved import sha

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def prove():
    first=HERE/'saved-fixtures'/'reference'
    second=HERE/'saved-fixtures'/'contrast'
    positive=compare(first,second)
    if (positive['source_kind']!='synthetic_cpu' or
            positive['paired_frames']!=240 or positive['accepted_comparison']):
        raise AssertionError('Synthetic rotary saved comparison differs')
    negatives=[]
    for mutation in ('island_readback','speed','body_mirror','camera_frame'):
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered=Path(temporary)/'contrast';shutil.copytree(second,altered)
            if mutation=='island_readback':
                path=altered/'island-readback.json';path.write_bytes(path.read_bytes()+b' ')
            elif mutation=='camera_frame':
                path=altered/'island-frames.jsonl';data=load(path)
                data[60]['camera_frame']=-1;write(path,data)
            else:
                path=altered/'native-observed.jsonl';data=load(path)
                if mutation=='speed':data[60]['ego_speed_mps']=9
                else:data[60]['ego_body_xy_m'][0][1]+=.2
                write(path,data)
            try:compare(first,altered)
            except (ValueError,TypeError,KeyError):
                negatives.append({'mutation':mutation,'rejected':True})
            else:raise AssertionError('Altered rotary saved pair accepted')
    proof={'format':'c234827-saved-comparison-proof-v1',
        'assignment_id':HERE.parent.name,
        'processor_sha256':sha(HERE/'compare_saved.py'),
        'positive':positive,'negative_controls':negatives,
        'original_native_observed':False,'accepted_comparison':False,
        'legal_verdict':None,'delivery_ready':False}
    (HERE/'saved-comparison-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    result=prove();print(json.dumps({'paired_frames':result['positive']['paired_frames'],
                                     'negatives':len(result['negative_controls'])}))
