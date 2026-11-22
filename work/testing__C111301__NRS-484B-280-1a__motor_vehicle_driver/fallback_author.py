"""Alternate asset lookup for a renamed Native manual-chair prop blueprint."""
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
MANIFEST=ROOT/'execution-manifest.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        primary=json.loads((ROOT/entry['construction']).read_text())
        alternate=json.loads(json.dumps(primary))
        scene_file=next(f for f in alternate['files'] if f['path']=='scene.json')
        scene=json.loads(scene_file['content'])
        scene['manual_chair_blueprint_filter']='static.prop.*wheelchair*'
        scene_file['content']=json.dumps(scene,indent=2)+'\n'
        config_file=next(f for f in alternate['files'] if f['path']=='config.json')
        config=json.loads(config_file['content'])
        config['manual_chair_blueprint_filter']=scene['manual_chair_blueprint_filter']
        config_file['content']=json.dumps(config,indent=2)+'\n'
        alternate['mechanisms'].append('Alternate Native wheelchair prop lookup for renamed asset IDs')
        label='clear' if entry['case_id'].endswith('clear_path') else 'crossing'
        path=ROOT/('fallback-'+label+'-construction.json')
        path.write_text(json.dumps(alternate,indent=2)+'\n')
        candidate={'id':'fallback1','construction':path.name,'construction_sha256':sha(path),
          'trigger':{'source':'Native CARLA blueprint library',
            'metric':'matching manual-wheelchair asset blueprint count',
            'failure_condition':'primary exact wheelchair prop filter returns zero matches'},
          'changed_knobs':['manual_chair_blueprint_filter: static.prop.wheelchair* -> static.prop.*wheelchair*']}
        prior=next((c for c in entry.get('candidates',[]) if c.get('id')=='fallback1'),{})
        for key in ('offline','compatibility'):
            if prior.get(key) and prior.get('construction_sha256')==candidate['construction_sha256']:
                candidate[key]=prior[key]
        entry['candidates']=[candidate]
    MANIFEST.write_text(json.dumps(manifest,indent=2)+'\n')


if __name__=='__main__':main()
