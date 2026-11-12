"""Include midpoint in the root config without changing base case config bytes."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
MID='testing__C101303__NRS-484B-127-1__motor_vehicle_driver__source_verified_midpoint'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((ROOT/'execution-manifest.json').read_text())
    if len(manifest['cases'])!=9:
        raise ValueError('Nine selected cases required')
    base=next(c for c in manifest['cases'] if c['case_id'].endswith('__source_verified_base'))
    construction=ROOT/base['construction']
    if sha(construction)!=base['construction_sha256']:
        raise ValueError('Selected base construction changed')
    bundle=json.loads(construction.read_text())
    config_row=next(x for x in bundle['files'] if x['path']=='config.json')
    old=json.loads(config_row['content'])
    if len(old['supported_case_ids'])!=8 or MID in old['supported_case_ids']:
        raise ValueError('Base case source config changed')
    archived=ROOT/'cases/source_verified_base/base-config-source.json'
    archived.parent.mkdir(parents=True,exist_ok=True)
    archived.write_text(config_row['content'])
    config_row['source']=str(archived.relative_to(REPO))
    construction.write_text(json.dumps(bundle,indent=2)+'\n')
    base['construction_sha256']=sha(construction)
    root_config=json.loads((ROOT/'config.json').read_text())
    if root_config!=old:
        raise ValueError('Root configuration no longer matches old base source')
    root_config['supported_case_ids'].append(MID)
    (ROOT/'config.json').write_text(json.dumps(root_config,indent=2)+'\n')
    root_bundle_path=ROOT/'construction.json'
    root_bundle=json.loads(root_bundle_path.read_text())
    next(x for x in root_bundle['files'] if x['path']=='config.json')['content']=(ROOT/'config.json').read_text()
    root_bundle_path.write_text(json.dumps(root_bundle,indent=2)+'\n')
    (ROOT/'root-config-rebind-candidate.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('root config includes midpoint; base exact config source archived',base['construction_sha256'])


if __name__=='__main__':
    main()
