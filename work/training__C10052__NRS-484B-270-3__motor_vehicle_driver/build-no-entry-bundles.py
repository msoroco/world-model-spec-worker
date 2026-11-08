"""Build four exact straight-through controls for the facility-entry branch."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NATIVE=HERE/'native'
SUFFIX='probe_d_no_entry'
NAMES=('primary','fallback1','fallback2','fallback3')


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source=json.loads((HERE/'draft-alley-execution-manifest.json').read_text())
    original=source['cases'][0]
    case_id=HERE.name+'__'+SUFFIX
    entry={'case_id':case_id,'kind':'draft_not_selected',
           'candidate_risk':{'status':'physical',
               'reason':'Original straight-route tracking, facility designation and pixels require Native evidence'},
           'measurement_procedure':{'entrypoint':'measure_entry.py',
                                    'output_schema':'c10052-moving-entry-measurement-v1'},
           'measurement_contract':'draft-no-entry-measurement-contract.json',
           'candidates':[]}
    for name in NAMES:
        ref=original if name=='primary' else next(c for c in original['candidates'] if c['id']==name)
        source_path=HERE/ref['construction']
        if sha(source_path)!=ref['construction_sha256']:
            raise ValueError('Source alley candidate construction hash differs')
        construction=json.loads(source_path.read_text())
        construction['case_id']=case_id
        construction['measurement_plan']={
            'method':'source-hashed 480-frame moving body/facility no-entry control',
            'status':'unselected_cpu_proposal'}
        construction['mechanisms']=[
            'authored bicycle facility and alley connector',
            'observed-pose straight driving-lane route',
            'four synchronized original source cameras']
        for item in construction['files']:
            if item['path'] in ('config.json','alley-native-config.json'):
                config=json.loads(item['content'])
                config['case_id']=case_id
                config['case_suffix']=SUFFIX
                config['selected_case_id']=case_id
                config['supported_case_ids']=[case_id]
                config['case']['case_id']=case_id
                config['case']['recording_description']=config['recording_description']
                item['content']=json.dumps(config,indent=2)+'\n'
            elif item['path']=='runner.py':
                item['content']=(NATIVE/'alley_runner.py').read_text()
            elif item['path']=='alley_geometry.py':
                item['content']=(NATIVE/'alley_geometry.py').read_text()
        output=HERE/'draft-no-entry-candidates'/SUFFIX/name/'construction.json'
        write(output,construction)
        exact={'id':name,'construction':str(output.relative_to(HERE)),
               'construction_sha256':sha(output)}
        if name=='primary':
            entry.update(exact)
        else:
            exact['trigger']=ref['trigger']
            exact['changed_knobs']=ref['changed_knobs']
            entry['candidates'].append(exact)
    manifest={'format':'worker-unselected-draft-construction-manifest-v1',
              'assignment_id':HERE.name,
              'runtime_manifest_sha256':source['runtime_manifest_sha256'],
              'status':'draft_not_selected','cases':[entry]}
    write(HERE/'draft-no-entry-execution-manifest.json',manifest)
    return {'case_id':case_id,'candidates':4,'manifest_sha256':sha(HERE/'draft-no-entry-execution-manifest.json')}


if __name__=='__main__':print(json.dumps(main(),indent=2))
