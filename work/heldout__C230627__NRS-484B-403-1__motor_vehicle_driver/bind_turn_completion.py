"""Bind an authored source-based 180-degree completion criterion to exact cases."""
from hashlib import sha256
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
MANIFEST=HERE/'execution-manifest.json'
CRITERION={'format':'worker-physical-completion-criteria',
           'criterion':'turn','motion_source':'trace.jsonl',
           'position_key':'position_m','heading_key':'heading_deg',
           'turn_degrees':180,'turn_tolerance_deg':30,
           'minimum_progress_m':1.0,'minimum_samples':2,
           'context_sources':[],
           'engineering_tolerances_not_legal':True}


def digest(path):return sha256(path.read_bytes()).hexdigest()


def update(name):
    path=HERE/name
    bundle=json.loads(path.read_text())
    configs=[item for item in bundle['files'] if item['path']=='config.json']
    if len(configs)!=1:raise ValueError('Exact construction config missing: '+name)
    config=json.loads(configs[0]['content'])
    config['physical_completion']=CRITERION
    content=json.dumps(config,indent=2)+'\n'
    configs[0]['content']=content
    path.write_text(json.dumps(bundle,indent=2)+'\n')
    suffix=name.removeprefix('construction-').removesuffix('.json')
    source=HERE/('source-construction-'+suffix+'-config.json')
    if source.is_file():source.write_text(content)
    if name=='construction.json':
        (HERE/'config.json').write_text(content)
    return digest(path)


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        entry['construction_sha256']=update(entry['construction'])
        for key in ('offline','compatibility','negative','delivery_acceptance',
                    'physical_preparation'):
            entry.pop(key,None)
        for candidate in entry['candidates']:
            candidate['construction_sha256']=update(candidate['construction'])
            for key in ('offline','compatibility'):
                candidate.pop(key,None)
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')
    print('Bound source-based 180-degree turn completion to',len(manifest['cases']),'exact cases')


if __name__=='__main__':main()
