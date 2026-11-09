"""Positive and material negative synthetic saved-processing probes."""
import json
from pathlib import Path
import tempfile

from build import CASES, HERE, POLICIES, put
from saved import process


def prove():
    positive=negative=0
    for suffix in CASES:
        for candidate in POLICIES:
            bundle=HERE/'drafts'/suffix/candidate
            source=HERE/'synthetic'/suffix/candidate/'raw.json'
            process(bundle,source);positive+=1
            baseline=json.loads(source.read_text())
            for mutation in ('case','config','frame','video','actor','body'):
                raw=json.loads(json.dumps(baseline))
                if mutation=='case':raw['case_id']+='-other'
                elif mutation=='config':raw['config_sha256']='0'*64
                elif mutation=='frame':raw['rows'][3]['frame']=4
                elif mutation=='video':raw['rows'][3]['video_frame']=4
                elif mutation=='actor':raw['rows'][3]['ego']['actor_id']=11
                else:raw['rows'][3]['ego']['body_xyz_m'][0][0]+=1
                with tempfile.TemporaryDirectory() as tmp:
                    path=Path(tmp)/'raw.json';put(path,raw)
                    try:process(bundle,path)
                    except ValueError:negative+=1
                    else:raise AssertionError('Saved mutation accepted: '+mutation)
    proof={'format':'c111662-4033-saved-proof-v1','positive_count':positive,
           'negative_count':negative,'frames_joined':positive*800,
           'synthetic_only':True,'delivery_ready':False}
    put(HERE/'saved-proof.json',proof)
    return proof


if __name__=='__main__':print(json.dumps(prove()))
