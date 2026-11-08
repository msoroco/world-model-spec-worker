"""Prove four controlled saved lane pairs and changed-speed rejection."""
import json
from pathlib import Path
import shutil
import tempfile

import compare_saved

CASE=Path(__file__).resolve().parent.parent

def prove():
    positives=[];negatives=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        receipt=compare_saved.compare(candidate)
        if receipt['delivery_ready'] or receipt['fixed_frame_speed_camera_rows']!=240:
            raise ValueError('C132497 controlled pair differs')
        positives.append(receipt)
        with tempfile.TemporaryDirectory() as temporary:
            altered=Path(temporary)
            for witness in ('reference','contrast'):
                source=CASE/'offline'/'bundles'/witness/candidate
                target=altered/'offline'/'bundles'/witness/candidate
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copytree(source,target)
            path=altered/'offline'/'bundles'/'contrast'/candidate/'config.json'
            config=json.loads(path.read_text());config['requested_speed_mps']+=1
            path.write_text(json.dumps(config)+'\n')
            try:compare_saved.compare(candidate,altered)
            except ValueError:negatives.append({'candidate_id':candidate,
                'mutation':'comparison_speed','rejected':True})
            else:raise ValueError('C132497 changed comparison speed accepted')
    proof={'format':'c132497-controlled-comparison-proof-v1',
        'positives':positives,'negatives':negatives,
        'original_native_observed':False,'delivery_ready':False}
    (CASE/'offline'/'proof-comparison.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    p=prove();print(json.dumps({'positives':len(p['positives']),
        'negatives':len(p['negatives'])}))
