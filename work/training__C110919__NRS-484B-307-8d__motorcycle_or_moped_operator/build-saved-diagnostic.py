"""Build an unselected current-camera diagnostic manifest for process-saved.

The earlier eight-bundle manifest remains historical. This rebinds the two
primary constructions to the current four-view names without asserting Native
capture or selected delivery readiness.
"""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES={'signal':'reference_corner','destination':'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    old=json.loads((HERE/'draft-execution-manifest.json').read_text())
    new={'format':'worker-unselected-saved-diagnostic-manifest-v1',
         'assignment_id':old['assignment_id'],
         'status':'draft_not_selected',
         'runtime_manifest_sha256':old['runtime_manifest_sha256'],
         'cases':[]}
    for condition,entry in zip(('condition_a','condition_b'),old['cases']):
        original=json.loads((HERE/entry['construction']).read_text())
        construction=json.loads(json.dumps(original))
        for item in construction['files']:
            if item['path']=='config.json':
                config=json.loads(item['content'])
                for camera in config['cameras']:
                    camera['name']=NAMES.get(camera['name'],camera['name'])
                config['knobs']['camera_profile']=[NAMES.get(name,name)
                                                   for name in config['knobs']['camera_profile']]
                # The saved missing-source feedback path reads this nested
                # descriptor to preserve the selected recording contract.
                config['case']['recording_description']=config['recording_description']
                item['content']=json.dumps(config,indent=2)+'\n'
            elif item['path'] in ('cameras.py','engineering.py','finalize.py'):
                code=item['content']
                for old_name,new_name in NAMES.items():
                    code=code.replace("'"+old_name+"'","'"+new_name+"'")
                item['content']=code
        target=HERE/'saved-diagnostic'/condition/'construction.json'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(construction,indent=2)+'\n')
        updated=dict(entry)
        updated['construction']=str(target.relative_to(HERE))
        updated['construction_sha256']=sha(target)
        updated['candidates']=[]
        updated['kind']='draft_not_selected'
        updated['camera_profile_status']='current_four_view_names_diagnostic'
        new['cases'].append(updated)
    target=HERE/'saved-diagnostic-manifest.json'
    target.write_text(json.dumps(new,indent=2)+'\n')
    print(json.dumps({'cases':len(new['cases']),'manifest_sha256':sha(target),
                      'construction_sha256':[e['construction_sha256'] for e in new['cases']]}))


if __name__=='__main__':
    main()
