"""Build one earlier-braking engineering fallback for linked distance probes."""
import hashlib
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
manifest_path=root/'execution-manifest.json'
manifest=json.loads(manifest_path.read_text())

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

for entry in manifest['cases']:
    case=entry['case_id'];suffix=case.rsplit('__',1)[-1]
    primary=json.loads((root/entry['construction']).read_text())
    alternate=json.loads(json.dumps(primary))
    alternate['candidate_id']='fallback1'
    for item in alternate['files']:
        if item['path']=='config.json':
            cfg=json.loads(item['content'])
            cfg['candidate_id']='fallback1'
            cfg['brake_lead_seconds']=1.8
            item['content']=json.dumps(cfg,indent=2,sort_keys=True)+'\n'
    alternate['mechanisms'].append('Earlier 1.8 s braking lead instead of primary 1.2 s lead')
    path=root/'native'/(suffix+'-fallback1-construction.json')
    path.write_text(json.dumps(alternate,indent=2,sort_keys=True)+'\n')
    entry['candidate_risk']={'status':'physical',
        'reason':'Open-loop primary brake timing may overshoot the requested signal approach gap on actual CARLA dynamics; original footprint and speed reveal the failure.'}
    entry['candidates']=[{'id':'fallback1','construction':str(path.relative_to(root)),
        'construction_sha256':sha(path),
        'trigger':{'source':'original Native signal_raw.json, trace.jsonl and finalizer target_checks',
                   'metric':'observed final front-edge signal approach gap minus requested gap',
                   'failure_condition':'Primary final rest misses engineering target by more than 0.2 m or crosses the signal station'},
        'changed_knobs':['brake_lead_seconds: 1.2 to 1.8; same target gap, signal, camera and subject'],
        'offline':{},'compatibility':{}}]
manifest_path.write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
