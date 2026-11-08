"""Independent rotary saved-pair rows and negative replay."""
import json
from pathlib import Path
import shutil
import tempfile

from compare_saved import compare
from measure_saved import sha

HERE=Path(__file__).resolve().parent


def load(path):return [json.loads(line) for line in path.read_text().splitlines()]
def write(path,values):path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in values))


def audit():
    path=HERE/'saved-comparison-proof.json';proof=json.loads(path.read_text())
    mutations=['island_readback','speed','body_mirror','camera_frame']
    if (proof['format']!='c234827-saved-comparison-proof-v1' or
            proof['assignment_id']!=HERE.parent.name or
            proof['processor_sha256']!=sha(HERE/'compare_saved.py') or
            [row['mutation'] for row in proof['negative_controls']]!=mutations or
            not all(row['rejected'] is True for row in proof['negative_controls']) or
            proof['original_native_observed'] or proof['accepted_comparison'] or
            proof['legal_verdict'] is not None or proof['delivery_ready']):
        raise ValueError('Rotary saved comparison proof differs')
    first=HERE/'saved-fixtures'/'reference'
    second=HERE/'saved-fixtures'/'contrast'
    if (first/'island-readback.json').read_bytes()!=(second/'island-readback.json').read_bytes():
        raise ValueError('Independent rotary fixed island differs')
    a,b=load(first/'native-observed.jsonl'),load(second/'native-observed.jsonl')
    if len(a)!=240 or len(b)!=240:raise ValueError('Rotary saved pair count differs')
    for i,(left,right) in enumerate(zip(a,b)):
        heading_sum=(left['ego_heading_deg']+right['ego_heading_deg'])%360
        left_body=sorted((round(x,4),round(-y,4)) for x,y in left['ego_body_xy_m'])
        right_body=sorted((round(x,4),round(y,4)) for x,y in right['ego_body_xy_m'])
        if (left['frame']!=i or right['frame']!=i or
                left['native_frame']!=right['native_frame'] or
                left['time_s']!=right['time_s'] or
                left['ego_speed_mps']!=right['ego_speed_mps'] or
                left['lane_id']!=right['lane_id'] or
                abs(left['ego_x_m']-right['ego_x_m'])>1e-5 or
                abs(left['ego_y_m']+right['ego_y_m'])>1e-5 or
                min(heading_sum,360-heading_sum)>1e-4 or
                left_body!=right_body):
            raise ValueError('Independent rotary saved pair row differs')
    if compare(first,second,proof['positive']['source_hashes'])!=proof['positive']:
        raise ValueError('Rotary saved comparison metric differs')
    replayed=[]
    for mutation in mutations:
        with tempfile.TemporaryDirectory(dir=HERE) as temporary:
            altered=Path(temporary)/'contrast';shutil.copytree(second,altered)
            if mutation=='island_readback':
                target=altered/'island-readback.json';target.write_bytes(target.read_bytes()+b' ')
            elif mutation=='camera_frame':
                target=altered/'island-frames.jsonl';data=load(target)
                data[60]['camera_frame']=-1;write(target,data)
            else:
                target=altered/'native-observed.jsonl';data=load(target)
                if mutation=='speed':data[60]['ego_speed_mps']=9
                else:data[60]['ego_body_xy_m'][0][1]+=.2
                write(target,data)
            try:compare(first,altered)
            except (ValueError,TypeError,KeyError):replayed.append(mutation)
            else:raise ValueError('Independent rotary saved comparison negative accepted')
    receipt={'format':'c234827-independent-saved-comparison-audit-v1',
        'proof_sha256':sha(path),'paired_rows_checked':480,
        'negative_controls_replayed':replayed,
        'original_native_observed':False,'accepted_comparison':False,
        'delivery_ready':False}
    (HERE/'saved-comparison-audit.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':print(json.dumps(audit()))
