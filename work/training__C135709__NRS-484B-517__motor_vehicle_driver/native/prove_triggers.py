"""Retain synthetic fallback signal variants and a changed-frame negative."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

import triggers

CASE=Path(__file__).resolve().parents[1]
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]
def write_rows(path,items):path.write_text(''.join(json.dumps(x)+'\n' for x in items))

def prove():
    bundle=CASE/'offline/bundles/reference/primary'
    base=bundle/'saved'
    variants=[]
    for name in ('entry_occluded','pose_deviation'):
        target=CASE/'native/trigger-fixtures'/name
        if target.exists():shutil.rmtree(target)
        shutil.copytree(base,target)
        if name=='entry_occluded':
            path=target/'camera-frames.jsonl';items=rows(path)
            for row in items[:30]:row['stand_sign_visible']=False
            write_rows(path,items)
        else:
            path=target/'stand-review.jsonl';items=rows(path)
            items[120]['reviewed_ego_y_m']+=.3
            write_rows(path,items)
            readback=target/'stand-readback.json';data=json.loads(readback.read_text())
            data['review_sha256']=sha(path)
            readback.write_text(json.dumps(data,indent=2)+'\n')
        result=triggers.route(bundle,target)
        expected='fallback1' if name=='entry_occluded' else 'fallback2'
        if result['triggered_candidate']!=expected:
            raise AssertionError('C135709 measured trigger did not fire')
        variants.append({'name':name,'triggered_candidate':expected,
            'source_hashes':{p.name:sha(p) for p in target.iterdir() if p.is_file()},
            'measurement':result})
    baseline=triggers.route(bundle)
    if baseline['triggered_candidate']!='fallback3':
        raise AssertionError('C135709 unverified statutory trigger absent')
    with tempfile.TemporaryDirectory(dir=CASE/'offline') as temporary:
        target=Path(temporary)/'saved';shutil.copytree(base,target)
        path=target/'stand-review.jsonl';items=rows(path)
        items[71]['native_frame']+=1;write_rows(path,items)
        readback=target/'stand-readback.json';data=json.loads(readback.read_text())
        data['review_sha256']=sha(path);readback.write_text(json.dumps(data)+'\n')
        try:triggers.route(bundle,target)
        except ValueError:pass
        else:raise AssertionError('C135709 changed reviewed frame accepted')
    proof={'format':'c135709-trigger-proof-v1','baseline':baseline,
        'variants':variants,'changed_frame_rejected':True,
        'original_native_observed':False,'candidate_selected_for_delivery':None,
        'delivery_ready':False}
    (CASE/'native/trigger-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':print(json.dumps({'variants':len(prove()['variants'])}))
