"""Eight positive and material negative copied-source request probes."""
import json
from pathlib import Path
import tempfile

from build import CASES, HERE, POLICIES, put, sha
from check import check


def prove():
    positives=negatives=0
    for suffix in CASES:
        for candidate in POLICIES:
            source=HERE/'drafts'/suffix/candidate
            check(source);positives+=1
            for mutation in ('law','road','track','status'):
                with tempfile.TemporaryDirectory() as temp:
                    bundle=Path(temp)
                    for file in source.iterdir():
                        (bundle/file.name).write_bytes(file.read_bytes())
                    cfg=json.loads((bundle/'config.json').read_text())
                    if mutation=='law':
                        path=bundle/'assignment-source.json'
                        data=json.loads(path.read_text());data['law_record']['text']+=' changed'
                        put(path,data)
                    elif mutation=='road':
                        path=bundle/'district-crossroads.xodr'
                        path.write_text(path.read_text().replace('x="-100"','x="-99"',1))
                        cfg['road_sha256']=sha(path);put(bundle/'config.json',cfg)
                    elif mutation=='track':
                        path=bundle/'requested-tracks.jsonl'
                        lines=path.read_text().splitlines();row=json.loads(lines[4]);row['requested_ego_xyz_m'][0]+=.2
                        lines[4]=json.dumps(row);path.write_text('\n'.join(lines)+'\n')
                        cfg['tracks_sha256']=sha(path);put(bundle/'config.json',cfg)
                    else:
                        cfg['status']='runnable';put(bundle/'config.json',cfg)
                    try:check(bundle)
                    except ValueError:negatives+=1
                    else:raise AssertionError('Mutation accepted: '+mutation)
    proof={"format":"c111662-4033-request-proof-v1","positive_count":positives,
           "negative_count":negatives,"original_native_observed":False,"delivery_ready":False}
    put(HERE/'request-proof.json',proof)
    return proof


if __name__=='__main__':print(json.dumps(prove()))
